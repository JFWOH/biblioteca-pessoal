"""Testes da rodada M2 do servidor MCP: escrita guardada + ask_library.

Invariantes cobertos: TODA escrita bloqueada com mcp.allow_writes=false
(default), toggle vale sem reiniciar (config relido a cada chamada), escrita
sempre aditiva com origem {"source": "mcp"}, ask_library serializado com
needs_reindex/Ollama virando erro amigável (sem exigir allow_writes).
"""

import json

import anyio
import pytest

from src.core.database import LibraryDB
from src.mcp import server


@pytest.fixture
def env(tmp_path):
    """DB real + config.json em tmp_path; servidor apontado para ambos."""
    db_path = tmp_path / "library.db"
    cfg_path = tmp_path / "config.json"
    seed = LibraryDB(db_path)
    b1 = seed.add_book(title="Dom Casmurro", author="Machado de Assis",
                       file_path=str(tmp_path / "dom.pdf"), file_format="pdf")
    b2 = seed.add_book(title="Vidas Secas", author="Graciliano Ramos",
                       file_path=str(tmp_path / "vidas.epub"), file_format="epub")
    seed.close()
    server.configure(db_path=db_path, config_path=cfg_path)
    yield {"tmp": tmp_path, "db_path": db_path, "cfg": cfg_path,
           "b1": b1, "b2": b2}
    server.close()


def _enable_writes(env):
    env["cfg"].write_text(json.dumps({"mcp": {"allow_writes": True}}),
                          encoding="utf-8")


def _db(env):
    return LibraryDB(env["db_path"])


WRITE_CALLS = [
    lambda b: server.add_annotation(b, 1, "nota"),
    lambda b: server.tag_book(b, "estoicismo"),
    lambda b: server.create_collection("Filosofia"),
    lambda b: server.add_to_collection(b, "Filosofia"),
    lambda b: server.set_reading_status(b, "reading"),
    lambda b: server.toggle_favorite(b),
]


class TestGuardaDeEscrita:
    def test_todas_as_escritas_bloqueadas_por_padrao(self, env):
        for call in WRITE_CALLS:
            result = call(env["b1"])
            assert result["status"] == "error", result
            assert "allow_writes" in result["error"]
        # nada foi gravado
        db = _db(env)
        try:
            assert db.get_annotations(env["b1"]) == []
            assert db.get_tags() == []
            assert db.get_collections() == []
            book = db.get_book(env["b1"])
            assert book["read_status"] == "unread"
            assert not book["is_favorite"]
        finally:
            db.close()

    def test_toggle_vale_sem_reiniciar_o_servidor(self, env):
        assert server.toggle_favorite(env["b1"])["status"] == "error"
        _enable_writes(env)
        assert server.toggle_favorite(env["b1"])["status"] == "success"
        # desligar também vale na hora
        env["cfg"].write_text(json.dumps({"mcp": {"allow_writes": False}}),
                              encoding="utf-8")
        assert server.toggle_favorite(env["b1"])["status"] == "error"


class TestAddAnnotation:
    def test_ai_note_com_origem_mcp(self, env):
        _enable_writes(env)
        result = server.add_annotation(env["b1"], 5, "Resumo do capítulo.",
                                       title="Síntese")
        assert result["status"] == "success"
        db = _db(env)
        try:
            rows = db.get_annotations(env["b1"])
        finally:
            db.close()
        assert len(rows) == 1
        ann = rows[0]
        assert ann["annotation_type"] == "ai_note"
        assert ann["page_number"] == 4  # 1-based na fronteira, 0-based no banco
        assert ann["title"] == "Síntese"
        assert ann["highlight_color"] == server.AI_NOTE_COLOR
        assert json.loads(ann["position_data"]) == {"source": "mcp"}

    def test_validacoes(self, env):
        _enable_writes(env)
        assert server.add_annotation(env["b1"], 1, "   ")["status"] == "error"
        assert server.add_annotation(env["b1"], 0, "x")["status"] == "error"
        assert server.add_annotation(99999, 1, "x")["status"] == "error"


class TestTagsEColecoes:
    def test_tag_book_cria_e_reusa_case_insensitive(self, env):
        _enable_writes(env)
        r1 = server.tag_book(env["b1"], "Estoicismo")
        assert r1["status"] == "success" and r1["data"]["created"] is True
        r2 = server.tag_book(env["b2"], "estoicismo")
        assert r2["status"] == "success" and r2["data"]["created"] is False
        assert r2["data"]["tag_id"] == r1["data"]["tag_id"]
        db = _db(env)
        try:
            assert len(db.get_tags()) == 1
            assert [t["name"] for t in db.get_book_tags(env["b2"])] == ["Estoicismo"]
        finally:
            db.close()

    def test_colecoes_criar_duplicar_e_vincular(self, env):
        _enable_writes(env)
        r = server.create_collection("Filosofia", description="clássicos")
        assert r["status"] == "success"
        coll_id = r["data"]["collection_id"]
        assert server.create_collection("filosofia")["status"] == "error"

        by_name = server.add_to_collection(env["b1"], "Filosofia")
        assert by_name["status"] == "success"
        by_id = server.add_to_collection(env["b2"], coll_id)
        assert by_id["status"] == "success"
        assert by_id["data"]["collection"] == "Filosofia"
        missing = server.add_to_collection(env["b1"], "Inexistente")
        assert missing["status"] == "error"
        assert "create_collection" in missing["error"]
        db = _db(env)
        try:
            books = db.get_books_in_collection(coll_id)
        finally:
            db.close()
        assert {b["id"] for b in books} == {env["b1"], env["b2"]}


class TestStatusEFavorito:
    def test_set_reading_status_whitelist(self, env):
        _enable_writes(env)
        assert server.set_reading_status(env["b1"], "reading")["status"] == "success"
        db = _db(env)
        try:
            assert db.get_book(env["b1"])["read_status"] == "reading"
        finally:
            db.close()
        assert server.set_reading_status(env["b1"], "lido")["status"] == "error"
        assert server.set_reading_status(99999, "read")["status"] == "error"

    def test_toggle_favorite_devolve_estado_final(self, env):
        _enable_writes(env)
        assert server.toggle_favorite(env["b1"])["data"]["is_favorite"] is True
        assert server.toggle_favorite(env["b1"])["data"]["is_favorite"] is False


class FakeEngine:
    def __init__(self, reindex=False):
        self._reindex = reindex

    def needs_reindex(self):
        return self._reindex


class FakeOrchestrator:
    def __init__(self, chunks=None, error=None, reindex=False):
        self.engine = FakeEngine(reindex)
        self._chunks = chunks or []
        self._error = error

    def query_rag(self, question, n_context=None, book_id=None,
                  ui_mutation_callback=None, status_callback=None):
        if self._error:
            raise self._error
        yield from self._chunks


class TestAskLibrary:
    def test_resposta_com_citacoes_resolvidas(self, env, monkeypatch):
        fake = FakeOrchestrator(chunks=[
            "O ciúme domina Bentinho ", "[Dom Casmurro, p. 5]",
            " e reaparece adiante [Dom Casmurro, p. 5].",
        ])
        monkeypatch.setattr(server, "_make_orchestrator", lambda: fake)
        result = server.ask_library("qual o tema central?")
        assert result["status"] == "success"
        data = result["data"]
        assert "ciúme" in data["answer"]
        # deduplicada e resolvida para o livro certo
        assert data["citations"] == [
            {"title": "Dom Casmurro", "page": 5, "book_id": env["b1"]}]

    def test_nao_exige_allow_writes(self, env, monkeypatch):
        # escrita segue OFF neste teste — perguntar é leitura
        monkeypatch.setattr(server, "_make_orchestrator",
                            lambda: FakeOrchestrator(chunks=["ok"]))
        assert server.ask_library("pergunta")["status"] == "success"

    def test_needs_reindex_vira_erro_amigavel(self, env, monkeypatch):
        monkeypatch.setattr(server, "_make_orchestrator",
                            lambda: FakeOrchestrator(reindex=True))
        result = server.ask_library("pergunta")
        assert result["status"] == "error"
        assert "Reindexe" in result["error"]

    def test_ollama_fora_vira_erro_amigavel_e_lock_libera(self, env, monkeypatch):
        monkeypatch.setattr(
            server, "_make_orchestrator",
            lambda: FakeOrchestrator(error=RuntimeError(
                "Ollama não está disponível. Inicie o daemon com 'ollama serve'.")))
        result = server.ask_library("pergunta")
        assert result["status"] == "error"
        assert "Ollama" in result["error"]
        # o lock foi liberado mesmo com erro — nova chamada funciona
        monkeypatch.setattr(server, "_make_orchestrator",
                            lambda: FakeOrchestrator(chunks=["depois do erro"]))
        assert server.ask_library("de novo")["status"] == "success"

    def test_pergunta_vazia(self, env):
        assert server.ask_library("  ")["status"] == "error"


class TestIntegracaoEscrita:
    """Escrita ponta-a-ponta via client session (schemas das novas tools)."""

    def test_add_annotation_via_client(self, env):
        from mcp.shared.memory import create_connected_server_and_client_session
        _enable_writes(env)

        async def scenario():
            async with create_connected_server_and_client_session(
                    server.mcp._mcp_server) as client:
                tools = await client.list_tools()
                names = {t.name for t in tools.tools}
                assert {"add_annotation", "tag_book", "create_collection",
                        "add_to_collection", "set_reading_status",
                        "toggle_favorite", "ask_library"} <= names
                result = await client.call_tool(
                    "add_annotation",
                    {"book_id": env["b1"], "page": 3, "content": "via client"})
                payload = json.loads(result.content[0].text)
                assert payload["status"] == "success"
                assert payload["data"]["page"] == 3

        anyio.run(scenario)
        db = _db(env)
        try:
            rows = db.get_annotations(env["b1"], annotation_type="ai_note")
        finally:
            db.close()
        assert len(rows) == 1 and rows[0]["page_number"] == 2
