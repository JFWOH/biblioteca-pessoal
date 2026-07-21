"""Testes do backend HTTP fino da Biblioteca Pessoal — rodada M0 (API mobile).

Padrão de fixture do MCP (``tests/test_mcp_server.py``): ``LibraryDB`` real em
``tmp_path``, com arquivos dummy reais para ``/read`` e uma capa dummy para
``/library/{id}/cover``, ``src.api.main.configure(db_path=..., token=...)`` e
``TestClient`` do FastAPI. Guarda estrutural: ``src/api/**`` não importa
PyQt6/GUI nem módulos pesados (chromadb/torch/RAGEngine) no nível de módulo.
"""

import ast
import importlib
import json
from pathlib import Path

import pytest
from fastapi.testclient import TestClient

from src.api import main as api_main
from src.core.database import LibraryDB

TOKEN = "tok-teste"


def _pdf_bytes() -> bytes:
    return b"%PDF-1.4 conteudo dummy para teste\n%%EOF"


def _auth_headers(token: str = TOKEN) -> dict:
    return {"Authorization": f"Bearer {token}"}


def _data(resp):
    body = resp.json()
    assert body["status"] == "success", body
    return body["data"]


@pytest.fixture
def api_client(tmp_path, monkeypatch):
    """LibraryDB real em tmp_path (2 livros, anotações, bookmark, FTS,
    progresso), arquivos dummy reais p/ /read e uma capa dummy p/ cover."""
    monkeypatch.delenv("BIBLIOTECA_API_TOKEN", raising=False)

    db_path = tmp_path / "library.db"
    seed = LibraryDB(db_path)

    book1_path = tmp_path / "dom.pdf"
    book1_path.write_bytes(_pdf_bytes())
    cover1_path = tmp_path / "cover1.jpg"
    cover1_path.write_bytes(b"fake-jpeg-bytes")
    b1 = seed.add_book(title="Dom Casmurro", author="Machado de Assis",
                       file_path=str(book1_path), file_format="pdf",
                       cover_path=str(cover1_path))

    book2_path = tmp_path / "vidas.epub"
    book2_path.write_bytes(b"fake epub bytes")
    b2 = seed.add_book(title="Vidas Secas", author="Graciliano Ramos",
                       file_path=str(book2_path), file_format="epub")
    seed.update_book(b2, is_favorite=1, rating=5, read_status="read")

    seed.add_annotation(b1, 4, content="Olhos de ressaca", annotation_type="note",
                        title="Capitu")
    seed.add_annotation(b1, 9, content="trecho destacado", annotation_type="highlight")
    seed.add_bookmark(b1, 2, label="Capítulo 2")
    seed.fts_index_book(b1, [(0, "A filosofia estoica ensina serenidade."),
                             (2, "Mais filosofia aplicada à vida.")])
    seed.update_reading_progress(b1, 2, 100, time_spent=60)
    seed.close()

    api_main.configure(db_path=db_path, config_path=tmp_path / "config.json",
                       token=TOKEN)
    with TestClient(api_main.app) as client:
        yield {"client": client, "tmp": tmp_path, "db_path": db_path,
               "b1": b1, "b2": b2, "book1_path": book1_path,
               "book2_path": book2_path}
    api_main.configure(token="")  # limpa o override — não vaza entre testes
    api_main.close()


class TestAuth:
    def test_sem_header_401(self, api_client):
        resp = api_client["client"].get("/library")
        assert resp.status_code == 401
        assert resp.json()["status"] == "error"

    def test_token_errado_401(self, api_client):
        resp = api_client["client"].get("/library", headers=_auth_headers("errado"))
        assert resp.status_code == 401

    def test_health_aberto(self, api_client):
        resp = api_client["client"].get("/health")
        assert resp.status_code == 200
        data = _data(resp)
        assert data["app"] == "biblioteca-api"

    def test_token_nao_configurado_503(self, tmp_path, monkeypatch):
        monkeypatch.delenv("BIBLIOTECA_API_TOKEN", raising=False)
        db_path = tmp_path / "library.db"
        LibraryDB(db_path).close()
        # token="" limpa qualquer override anterior e bloqueia o fallback
        # para env/config — força o caminho "não configurado".
        api_main.configure(db_path=db_path, config_path=tmp_path / "config.json",
                           token="")
        try:
            with TestClient(api_main.app) as client:
                resp = client.get("/library", headers=_auth_headers("qualquer"))
                assert resp.status_code == 503
                assert resp.json()["status"] == "error"
        finally:
            api_main.close()


class TestConfigureTokenSemantics:
    """configure(token=None) NÃO reseta o override para env/config;
    configure(token="") limpa explicitamente (ver docstring de configure())."""

    def test_none_preserva_e_string_vazia_limpa(self, tmp_path, monkeypatch):
        monkeypatch.delenv("BIBLIOTECA_API_TOKEN", raising=False)
        db_path = tmp_path / "library.db"
        LibraryDB(db_path).close()
        try:
            api_main.configure(db_path=db_path, token="tok-fixo")
            assert api_main._resolve_token() == "tok-fixo"

            api_main.configure(db_path=db_path, token=None)
            assert api_main._resolve_token() == "tok-fixo"  # preservado

            api_main.configure(db_path=db_path, token="")
            assert api_main._resolve_token() is None  # limpo explicitamente
        finally:
            api_main.close()


class TestLibrary:
    def test_listagem_total_percentage_sem_file_path(self, api_client):
        c = api_client["client"]
        resp = c.get("/library", headers=_auth_headers())
        assert resp.status_code == 200
        data = _data(resp)
        assert data["total"] == 2
        assert data["returned"] == 2
        for book in data["books"]:
            assert "file_path" not in book
            assert "percentage" in book

    def test_filtros(self, api_client):
        c = api_client["client"]
        h = _auth_headers()
        assert _data(c.get("/library", params={"status": "read"}, headers=h))["total"] == 1
        assert _data(c.get("/library", params={"author": "graciliano"}, headers=h))["total"] == 1
        assert _data(c.get("/library", params={"favorites_only": "true"}, headers=h))["total"] == 1
        assert _data(c.get("/library", params={"min_rating": 5}, headers=h))["total"] == 1
        assert _data(c.get("/library", params={"file_format": ".EPUB"}, headers=h))["total"] == 1
        # b1 tem progresso setado no fixture (2%) -> status "reading";
        # nenhum livro fica "unread".
        assert _data(c.get("/library", params={"status": "reading"}, headers=h))["total"] == 1
        assert _data(c.get("/library", params={"status": "unread"}, headers=h))["total"] == 0

    def test_sort_e_paginacao(self, api_client):
        c = api_client["client"]
        h = _auth_headers()
        data = _data(c.get("/library", params={"sort_by": "title", "sort_order": "asc"},
                           headers=h))
        assert [b["title"] for b in data["books"]] == ["Dom Casmurro", "Vidas Secas"]
        page = _data(c.get("/library", params={"sort_by": "title", "sort_order": "asc",
                                                "limit": 1, "offset": 1}, headers=h))
        assert page["total"] == 2
        assert page["returned"] == 1
        assert page["books"][0]["title"] == "Vidas Secas"

    def test_detalhe_ok_progress_1based(self, api_client):
        c = api_client["client"]
        b1 = api_client["b1"]
        resp = c.get(f"/library/{b1}", headers=_auth_headers())
        assert resp.status_code == 200
        data = _data(resp)
        assert data["title"] == "Dom Casmurro"
        assert "file_path" not in data
        assert "cover_path" not in data
        assert data["annotations_count"] == 2
        assert data["progress"]["page"] == 3  # armazenado current_page=2 (0-based)
        assert "tags" in data and "collections" in data

    def test_detalhe_404(self, api_client):
        resp = api_client["client"].get("/library/99999", headers=_auth_headers())
        assert resp.status_code == 404
        assert resp.json()["status"] == "error"

    def test_cover_200_e_404(self, api_client):
        c = api_client["client"]
        resp = c.get(f"/library/{api_client['b1']}/cover", headers=_auth_headers())
        assert resp.status_code == 200
        resp = c.get(f"/library/{api_client['b2']}/cover", headers=_auth_headers())
        assert resp.status_code == 404


class TestRead:
    def test_200_bytes(self, api_client):
        resp = api_client["client"].get(f"/read/{api_client['b1']}", headers=_auth_headers())
        assert resp.status_code == 200
        assert resp.content == _pdf_bytes()

    def test_404_livro_inexistente(self, api_client):
        resp = api_client["client"].get("/read/99999", headers=_auth_headers())
        assert resp.status_code == 404

    def test_404_arquivo_sumido(self, api_client):
        api_client["book2_path"].unlink()
        resp = api_client["client"].get(f"/read/{api_client['b2']}", headers=_auth_headers())
        assert resp.status_code == 404


class TestProgress:
    def test_get_vazio_page_none(self, api_client):
        resp = api_client["client"].get(f"/progress/{api_client['b2']}",
                                        headers=_auth_headers())
        assert resp.status_code == 200
        data = _data(resp)
        assert data["page"] is None
        assert data["percentage"] == 0.0

    def test_post_e_get_consistentes_armazenado_0based(self, api_client):
        c = api_client["client"]
        b2 = api_client["b2"]
        resp = c.post(f"/progress/{b2}", json={"page": 5, "total_pages": 100, "seconds": 30},
                     headers=_auth_headers())
        assert resp.status_code == 200
        assert _data(resp)["page"] == 5

        db = LibraryDB(api_client["db_path"])
        row = db.get_reading_progress(b2)
        db.close()
        assert row["current_page"] == 4  # 1-based 5 -> armazenado 4

        resp = c.get(f"/progress/{b2}", headers=_auth_headers())
        assert _data(resp)["page"] == 5

    def test_seconds_clamp_300(self, api_client):
        c = api_client["client"]
        resp = c.post(f"/progress/{api_client['b2']}",
                      json={"page": 5, "total_pages": 100, "seconds": 999},
                      headers=_auth_headers())
        assert _data(resp)["time_spent_seconds"] == 300

    def test_page_invalida_422_ou_400(self, api_client):
        resp = api_client["client"].post(f"/progress/{api_client['b2']}",
                                         json={"page": 0, "total_pages": 100},
                                         headers=_auth_headers())
        assert resp.status_code in (400, 422)

    def test_livro_inexistente_404(self, api_client):
        c = api_client["client"]
        h = _auth_headers()
        assert c.post("/progress/99999", json={"page": 1, "total_pages": 10},
                      headers=h).status_code == 404
        assert c.get("/progress/99999", headers=h).status_code == 404

    def test_transicao_para_read(self, api_client):
        c = api_client["client"]
        b1 = api_client["b1"]
        # current_page (0-based) = page-1 = 10, total_pages=10 -> pct=100%
        # (>= 99.5%) cruza para "read" — mesma convenção 1-based/0-based da
        # fronteira, current_page pode alcançar total_pages na última página.
        resp = c.post(f"/progress/{b1}", json={"page": 11, "total_pages": 10},
                     headers=_auth_headers())
        assert resp.status_code == 200
        db = LibraryDB(api_client["db_path"])
        book = db.get_book(b1)
        db.close()
        assert book["read_status"] == "read"


class TestAnnotations:
    def test_get_paginas_1based_com_bookmarks(self, api_client):
        resp = api_client["client"].get(f"/annotations/{api_client['b1']}",
                                        headers=_auth_headers())
        assert resp.status_code == 200
        data = _data(resp)
        assert len(data["annotations"]) == 2
        assert data["annotations"][0]["page"] == 5  # armazenado 4
        assert data["annotations"][0]["title"] == "Capitu"
        assert len(data["bookmarks"]) == 1
        assert data["bookmarks"][0]["page"] == 3  # armazenado 2

    def test_post_cria_com_source_mobile(self, api_client):
        c = api_client["client"]
        b1 = api_client["b1"]
        resp = c.post(f"/annotations/{b1}", json={"page": 7, "content": "nota mobile"},
                     headers=_auth_headers())
        assert resp.status_code == 200
        data = _data(resp)
        assert data["annotation_type"] == "note"  # default
        assert data["page"] == 7

        db = LibraryDB(api_client["db_path"])
        row = db.conn.execute("SELECT position_data FROM annotations WHERE id=?",
                              (data["annotation_id"],)).fetchone()
        db.close()
        assert json.loads(row["position_data"])["source"] == "mobile"

    def test_content_vazio_400(self, api_client):
        resp = api_client["client"].post(f"/annotations/{api_client['b1']}",
                                         json={"page": 1, "content": "   "},
                                         headers=_auth_headers())
        assert resp.status_code == 400

    def test_livro_inexistente_404(self, api_client):
        resp = api_client["client"].get("/annotations/99999", headers=_auth_headers())
        assert resp.status_code == 404


class TestSearch:
    def test_fts_acha_seed_pagina_1based(self, api_client):
        resp = api_client["client"].get("/search", params={"q": "filosofia"},
                                        headers=_auth_headers())
        assert resp.status_code == 200
        data = _data(resp)
        assert data["total"] == 2
        assert data["results"][0]["page"] in (1, 3)  # armazenado 0-based (0, 2)

    def test_fts_query_vazia_total_0(self, api_client):
        resp = api_client["client"].get("/search", params={"q": ""}, headers=_auth_headers())
        assert _data(resp)["total"] == 0

    def test_semantic_erro_runtime_vira_503(self, api_client):
        class FakeRag:
            def search_similar(self, query, n_results=5, book_id=None):
                raise RuntimeError("Ollama indisponível para gerar embeddings.")

        api_main._state["rag"] = FakeRag()
        resp = api_client["client"].get(
            "/search", params={"q": "estoicismo", "mode": "semantic"},
            headers=_auth_headers())
        assert resp.status_code == 503
        assert "Ollama" in resp.json()["error"]


class TestStats:
    def test_campos_principais(self, api_client):
        resp = api_client["client"].get("/stats", headers=_auth_headers())
        assert resp.status_code == 200
        data = _data(resp)
        assert data["total"] == 2
        assert "streak" in data
        assert "weekly_minutes" in data


class TestOPDS:
    def test_feed_sem_auth(self, api_client):
        resp = api_client["client"].get("/opds")
        assert resp.status_code == 200
        assert b"<feed" in resp.content
        assert b"Dom Casmurro" in resp.content

    def test_download_200(self, api_client):
        resp = api_client["client"].get(f"/opds/download/{api_client['b1']}")
        assert resp.status_code == 200
        assert resp.content == _pdf_bytes()


class TestConstantsDataDirOverride:
    def test_env_override_recarrega_data_dir(self, tmp_path, monkeypatch):
        override = tmp_path / "custom_data"
        monkeypatch.setenv("BIBLIOTECA_DATA_DIR", str(override))
        import src.utils.constants as constants
        try:
            importlib.reload(constants)
            assert constants.DATA_DIR == override
            assert constants.DB_PATH == override / "library.db"
        finally:
            monkeypatch.delenv("BIBLIOTECA_DATA_DIR", raising=False)
            importlib.reload(constants)  # nunca vaza o override p/ outros testes


class TestGuardaEstrutural:
    """src/api/** não importa PyQt6/GUI em nenhum nível, nem módulos pesados
    (chromadb/torch/RAGEngine) no nível de módulo (startup leve — lição B0)."""

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

    def test_sem_gui_e_sem_pesados_no_topo(self):
        src_dir = Path(__file__).resolve().parent.parent / "src" / "api"
        files = list(src_dir.rglob("*.py"))
        assert files, "src/api vazio?"
        for f in files:
            tree = ast.parse(f.read_text(encoding="utf-8"), filename=str(f))
            for node in ast.walk(tree):
                for mod in self._imports(node):
                    for banned in self.FORBIDDEN_ANYWHERE:
                        assert not (mod == banned or mod.startswith(banned + ".")), (
                            f"{f.name}: import proibido: {mod}")
            for node in tree.body:
                for mod in self._imports(node):
                    for heavy in self.HEAVY_TOPLEVEL:
                        assert not (mod == heavy or mod.startswith(heavy + ".")), (
                            f"{f.name}: import pesado no nível de módulo: {mod}")
