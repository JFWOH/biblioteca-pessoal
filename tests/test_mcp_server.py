"""Testes do servidor MCP local (rodada M1 — somente leitura).

As funções-ferramenta são testadas diretamente (o decorator do FastMCP
devolve a própria função registrada); a integração roda servidor + client
session do SDK in-process (streams de memória, equivalentes aos pipes stdio,
sem subprocesso). Guarda estrutural: ``src/mcp/**`` não importa PyQt6/GUI em
nenhum nível, nem módulos pesados no nível de módulo (startup leve).
"""

import ast
import json
from pathlib import Path

import anyio
import pytest

from src.core.database import LibraryDB
from src.mcp import server


@pytest.fixture
def mcp_db(tmp_path):
    """LibraryDB real em tmp_path (2 livros, anotações e FTS), servidor apontado."""
    db_path = tmp_path / "library.db"
    seed = LibraryDB(db_path)
    b1 = seed.add_book(title="Dom Casmurro", author="Machado de Assis",
                       file_path=str(tmp_path / "dom.pdf"), file_format="pdf")
    b2 = seed.add_book(title="Vidas Secas", author="Graciliano Ramos",
                       file_path=str(tmp_path / "vidas.epub"), file_format="epub")
    seed.update_book(b2, is_favorite=1, rating=5, read_status="read")
    seed.add_annotation(b1, 4, content="Olhos de ressaca", annotation_type="note",
                        title="Capitu")
    seed.add_annotation(b1, 9, content="trecho destacado",
                        annotation_type="highlight")
    seed.fts_index_book(b1, [(0, "A filosofia estoica ensina serenidade."),
                             (2, "Mais filosofia aplicada à vida.")])
    seed.close()
    server.configure(db_path=db_path)
    yield {"tmp": tmp_path, "db_path": db_path, "b1": b1, "b2": b2}
    server.close()


def _data(result):
    assert result["status"] == "success", result
    return result["data"]


class TestListBooks:
    def test_lista_todos(self, mcp_db):
        data = _data(server.list_books())
        assert data["total"] == 2
        assert {b["title"] for b in data["books"]} == {"Dom Casmurro", "Vidas Secas"}
        # listagem enxuta: sem file_path
        assert "file_path" not in data["books"][0]

    def test_filtros(self, mcp_db):
        assert _data(server.list_books(status="read"))["total"] == 1
        assert _data(server.list_books(author="graciliano"))["total"] == 1
        assert _data(server.list_books(favorites_only=True))["total"] == 1
        assert _data(server.list_books(min_rating=5))["total"] == 1
        assert _data(server.list_books(file_format=".EPUB"))["total"] == 1
        assert _data(server.list_books(status="reading"))["total"] == 0

    def test_sort_e_paginacao(self, mcp_db):
        data = _data(server.list_books(sort_by="title", sort_order="asc"))
        assert [b["title"] for b in data["books"]] == ["Dom Casmurro", "Vidas Secas"]
        page = _data(server.list_books(sort_by="title", sort_order="asc",
                                       limit=1, offset=1))
        assert page["total"] == 2
        assert page["returned"] == 1
        assert page["books"][0]["title"] == "Vidas Secas"


class TestGetBook:
    def test_detalhes(self, mcp_db):
        data = _data(server.get_book(mcp_db["b1"]))
        assert data["book"]["title"] == "Dom Casmurro"
        assert data["annotations_count"] == 2
        assert data["fts_indexed"] is True
        assert "tags" in data and "collections" in data

    def test_nao_encontrado(self, mcp_db):
        result = server.get_book(99999)
        assert result["status"] == "error"
        assert "não encontrado" in result["error"]


class TestBuscas:
    def test_search_books_metadados(self, mcp_db):
        data = _data(server.search_books("Machado"))
        assert data["total"] == 1
        assert data["books"][0]["title"] == "Dom Casmurro"

    def test_search_books_query_invalida_vira_erro_amigavel(self, mcp_db):
        result = server.search_books('"aspas desbalanceadas')
        assert result["status"] == "error"

    def test_search_content_snippets_e_pagina_1based(self, mcp_db):
        data = _data(server.search_content("filosofia"))
        assert data["total"] == 2
        first = data["results"][0]
        assert first["book_id"] == mcp_db["b1"]
        assert first["book_title"] == "Dom Casmurro"
        assert first["page"] in (1, 3)  # armazenado 0-based (0 e 2)
        assert "filosofia" in first["snippet"].lower()
        # b2 não tem conteúdo indexado → nota de cobertura parcial
        assert "note" in data

    def test_search_content_prefixo(self, mcp_db):
        data = _data(server.search_content("filos"))
        assert data["total"] == 2


class FakeRag:
    def __init__(self, error=None, rows=None):
        self._error = error
        self._rows = rows or []

    def search_similar(self, query, n_results=5, book_id=None):
        if self._error:
            raise self._error
        return self._rows


class TestSemanticSearch:
    def test_erro_runtime_vira_envelope(self, mcp_db):
        server._state["rag"] = FakeRag(
            error=RuntimeError("Ollama não está disponível para gerar embeddings."))
        result = server.semantic_search("estoicismo")
        assert result["status"] == "error"
        assert "Ollama" in result["error"]

    def test_sucesso_converte_pagina(self, mcp_db):
        server._state["rag"] = FakeRag(rows=[{
            "document": "trecho sobre estoicismo",
            "metadata": {"book_id": mcp_db["b1"], "page_number": 0,
                         "chunk_type": "content"},
            "distance": 0.12,
        }])
        data = _data(server.semantic_search("estoicismo"))
        assert data["total"] == 1
        assert data["results"][0]["page"] == 1
        assert data["results"][0]["book_id"] == mcp_db["b1"]


def _make_pdf(path: Path, texts: list[str]) -> None:
    import fitz
    doc = fitz.open()
    for t in texts:
        page = doc.new_page()
        if t:
            page.insert_text((72, 72), t)
    doc.save(str(path))
    doc.close()


class TestGetPageText:
    def test_pdf_intervalo(self, mcp_db):
        pdf = mcp_db["tmp"] / "real.pdf"
        _make_pdf(pdf, ["Pagina um conteudo", "Pagina dois conteudo",
                        "Pagina tres conteudo"])
        db = LibraryDB(mcp_db["db_path"])
        bid = db.add_book(title="Real", file_path=str(pdf), file_format="pdf")
        db.close()
        data = _data(server.get_page_text(bid, 1, 2))
        assert data["total_pages"] == 3
        assert [p["page"] for p in data["pages"]] == [1, 2]
        assert "Pagina um" in data["pages"][0]["text"]
        # clamp: pedir além do fim devolve só o que existe
        data = _data(server.get_page_text(bid, 2, 10))
        assert [p["page"] for p in data["pages"]] == [2, 3]

    def test_teto_de_10_paginas(self, mcp_db):
        result = server.get_page_text(mcp_db["b1"], 1, 11)
        assert result["status"] == "error"
        assert "10" in result["error"]

    def test_intervalo_invalido_e_livro_ausente(self, mcp_db):
        assert server.get_page_text(mcp_db["b1"], 3, 1)["status"] == "error"
        assert server.get_page_text(mcp_db["b1"], 0, 1)["status"] == "error"
        assert server.get_page_text(99999, 1)["status"] == "error"
        # b1 tem file_path que não existe no disco
        result = server.get_page_text(mcp_db["b1"], 1)
        assert result["status"] == "error"
        assert "disco" in result["error"]

    def test_fallback_cache_ocr(self, mcp_db):
        pdf = mcp_db["tmp"] / "scanned.pdf"
        _make_pdf(pdf, [""])  # página sem texto nativo
        db = LibraryDB(mcp_db["db_path"])
        bid = db.add_book(title="Escaneado", file_path=str(pdf), file_format="pdf")
        db.save_ocr_page(bid, 0, "texto recuperado por ocr")
        db.close()
        data = _data(server.get_page_text(bid, 1))
        assert data["pages"][0]["text"] == "texto recuperado por ocr"

    def test_txt_fallback_get_page_html(self, mcp_db):
        txt = mcp_db["tmp"] / "notas.txt"
        txt.write_text("Primeira linha do arquivo texto.\nSegunda linha.",
                       encoding="utf-8")
        db = LibraryDB(mcp_db["db_path"])
        bid = db.add_book(title="Notas", file_path=str(txt), file_format="txt")
        db.close()
        data = _data(server.get_page_text(bid, 1))
        assert "Primeira linha" in data["pages"][0]["text"]

    def test_epub_get_chapter_text(self, mcp_db):
        from ebooklib import epub
        book = epub.EpubBook()
        book.set_identifier("t1")
        book.set_title("EPUB Teste")
        book.set_language("pt")
        ch = epub.EpubHtml(title="Cap 1", file_name="c1.xhtml",
                           content="<h1>Cap 1</h1><p>Texto do capitulo um.</p>")
        book.add_item(ch)
        book.toc = (ch,)
        book.spine = ["nav", ch]
        book.add_item(epub.EpubNcx())
        book.add_item(epub.EpubNav())
        path = mcp_db["tmp"] / "livro.epub"
        epub.write_epub(str(path), book)
        db = LibraryDB(mcp_db["db_path"])
        bid = db.add_book(title="EPUB Teste", file_path=str(path),
                          file_format="epub")
        db.close()
        data = _data(server.get_page_text(bid, 1, 10))
        joined = " ".join(p["text"].lower() for p in data["pages"])
        assert "capitulo um" in joined


class TestAnotacoes:
    def test_list_annotations_pagina_1based(self, mcp_db):
        data = _data(server.list_annotations(mcp_db["b1"]))
        assert data["total"] == 2
        assert data["annotations"][0]["page"] == 5  # armazenado como 4 (0-based)
        assert data["annotations"][0]["title"] == "Capitu"

    def test_filtro_por_tipo_e_livro_ausente(self, mcp_db):
        data = _data(server.list_annotations(mcp_db["b1"],
                                             annotation_type="highlight"))
        assert data["total"] == 1
        assert data["annotations"][0]["type"] == "highlight"
        assert server.list_annotations(99999)["status"] == "error"

    def test_export_markdown(self, mcp_db):
        data = _data(server.export_annotations_markdown(mcp_db["b1"]))
        md = data["markdown"]
        assert "Dom Casmurro" in md
        assert "Olhos de ressaca" in md
        assert "Página 5" in md
        assert server.export_annotations_markdown(99999)["status"] == "error"


class TestLibraryStats:
    def test_estatisticas_compostas(self, mcp_db):
        data = _data(server.library_stats())
        assert data["total"] == 2
        assert data["read"] == 1
        assert data["favorites"] == 1
        assert data["streak_days"] == 0
        assert isinstance(data["weekly_minutes"], list)
        assert data["fts"] == {"pages": 2, "books": 1}
        assert data["fts_pending_books"] == 1


class TestIntegracaoClientSession:
    """Servidor + client session do SDK in-process (list/search/get + resource)."""

    def test_fluxo_completo(self, mcp_db):
        from mcp.shared.memory import create_connected_server_and_client_session

        async def scenario():
            async with create_connected_server_and_client_session(
                    server.mcp._mcp_server) as client:
                tools = await client.list_tools()
                names = {t.name for t in tools.tools}
                assert {"list_books", "get_book", "search_books",
                        "search_content", "semantic_search", "get_page_text",
                        "list_annotations", "export_annotations_markdown",
                        "library_stats"} <= names

                result = await client.call_tool("list_books", {})
                payload = json.loads(result.content[0].text)
                assert payload["status"] == "success"
                assert payload["data"]["total"] == 2

                result = await client.call_tool(
                    "get_book", {"book_id": mcp_db["b1"]})
                payload = json.loads(result.content[0].text)
                assert payload["data"]["book"]["title"] == "Dom Casmurro"

                result = await client.call_tool(
                    "search_content", {"query": "filosofia"})
                payload = json.loads(result.content[0].text)
                assert payload["data"]["total"] == 2

                from pydantic import AnyUrl
                res = await client.read_resource(AnyUrl("biblioteca://stats"))
                stats = json.loads(res.contents[0].text)
                assert stats["total"] == 2

        anyio.run(scenario)


class TestGuardaEstrutural:
    """ADR-006 + lição B0: src/mcp/** sem Qt/GUI e sem imports pesados no topo."""

    FORBIDDEN_ANYWHERE = ("PyQt6", "src.gui")
    HEAVY_TOPLEVEL = ("torch", "chromadb", "transformers", "kokoro",
                      "src.core.rag_engine", "src.readers", "bs4")

    @staticmethod
    def _imports(node):
        if isinstance(node, ast.Import):
            return [alias.name for alias in node.names]
        if isinstance(node, ast.ImportFrom):
            return [node.module or ""]
        return []

    def test_sem_gui_em_nenhum_nivel_e_sem_pesados_no_topo(self):
        src_dir = Path(__file__).resolve().parent.parent / "src" / "mcp"
        files = list(src_dir.rglob("*.py"))
        assert files, "src/mcp vazio?"
        for f in files:
            tree = ast.parse(f.read_text(encoding="utf-8"), filename=str(f))
            for node in ast.walk(tree):
                for mod in self._imports(node):
                    for banned in self.FORBIDDEN_ANYWHERE:
                        assert not (mod == banned or mod.startswith(banned + ".")), (
                            f"{f.name}: import proibido pela ADR-006: {mod}")
            for node in tree.body:
                for mod in self._imports(node):
                    for heavy in self.HEAVY_TOPLEVEL:
                        assert not (mod == heavy or mod.startswith(heavy + ".")), (
                            f"{f.name}: import pesado no nível de módulo "
                            f"(startup do MCP deve ser leve): {mod}")
