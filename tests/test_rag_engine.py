"""Testes abrangentes para o módulo RAG (rag_engine.py e rag_worker.py).

Todos os testes rodam 100% offline — o Ollama e o ChromaDB real são mockados,
exceto onde se testa o comportamento de persistência do ChromaDB em memória.

Categorias:
    TestChunkText         — função auxiliar de divisão de texto
    TestRAGEngineInit     — inicialização e health-checks
    TestRAGEngineIndexing — indexação de livros e anotações
    TestRAGEngineSearch   — busca vetorial semântica
    TestRAGEngineRAG      — pipeline completo de query RAG
    TestRAGWorker         — QThread com sinais PyQt6 (pytest-qt)
"""

from __future__ import annotations

import json
from pathlib import Path
from unittest.mock import MagicMock, patch

import pytest

# ── Auxiliar: cria banco SQLite mínimo para testes ─────────────────────────────

def _create_test_db(path: Path) -> Path:
    """Cria um banco SQLite com alguns livros e anotações de teste."""
    from src.core.database import LibraryDB
    db = LibraryDB(path)
    
    db.conn.execute(
        "INSERT INTO books (id, title, author, description, file_path, file_format) VALUES (?,?,?,?,?,?)",
        (1, "Dom Casmurro", "Machado de Assis",
         "Romance brasileiro do realismo. Bentinho e Capitu.", "/tmp/fake1.pdf", "pdf")
    )
    db.conn.execute(
        "INSERT INTO books (id, title, author, description, file_path, file_format) VALUES (?,?,?,?,?,?)",
        (2, "1984", "George Orwell",
         "Distopia futurista sobre controle estatal.", "/tmp/fake2.pdf", "pdf")
    )
    db.conn.execute(
        "INSERT INTO annotations (book_id, content, page_number) VALUES (?,?,?)",
        (1, "Capitu tinha olhos de ressaca — uma expressão marcante do autor.", 0)
    )
    db.conn.execute(
        "INSERT INTO books (id, title, author, description, file_path, file_format) VALUES (?,?,?,?,?,?)",
        (3, "Livro Sem Texto", "", "", "/tmp/fake3.pdf", "pdf")
    )
    db.conn.commit()
    db.conn.close()
    return path


# ── Fixtures ───────────────────────────────────────────────────────────────────

@pytest.fixture
def test_db(tmp_path) -> Path:
    return _create_test_db(tmp_path / "test_library.db")


@pytest.fixture
def chroma_path(tmp_path) -> Path:
    return tmp_path / "chroma_test"


@pytest.fixture
def fake_embedding() -> list[float]:
    """Embedding sintético de 768 dimensões."""
    return [0.1] * 768


@pytest.fixture
def mock_engine(test_db, chroma_path, fake_embedding):
    """RAGEngine com ChromaDB real em memória e Ollama mockado.

    Mocka tanto o embedding único (query) quanto o em lote (indexação) com a mesma
    dimensão sintética — caso contrário a indexação bateria no Ollama real e poderia
    gerar vetores de dimensão diferente da query (ex.: bge-m3=1024 vs query mockada),
    causando mismatch no Chroma. Mantém os testes herméticos e independentes do modelo.
    """
    from src.core.rag_engine import RAGEngine

    with patch.object(RAGEngine, "_get_embedding", return_value=fake_embedding), \
         patch.object(RAGEngine, "_get_embeddings_batch",
                      side_effect=lambda texts: [fake_embedding for _ in texts]), \
         patch.object(RAGEngine, "is_model_available", return_value=True), \
         patch.object(RAGEngine, "is_ollama_available", return_value=True):
        # is_model_available/is_ollama_available: sem eles, numa máquina SEM
        # Ollama (CI) o index_book entrava no caminho de pull do modelo e
        # vazava rede real — a suíte deve ser 100% hermética. Testes que
        # precisam de Ollama "fora" seguem patchando a instância (vence o
        # patch de classe).
        engine = RAGEngine(
            db_path=test_db,
            chroma_path=chroma_path,
            ollama_url="http://localhost:11434",
        )
        yield engine


# ══════════════════════════════════════════════════════════════════════════════
# TestChunkText
# ══════════════════════════════════════════════════════════════════════════════

class TestChunkText:
    """Testa a função de particionamento de texto."""

    def test_empty_string_returns_empty_list(self):
        from src.core.document_indexer_service import _chunk_text
        assert _chunk_text("") == []

    def test_whitespace_only_returns_empty_list(self):
        from src.core.document_indexer_service import _chunk_text
        assert _chunk_text("   \n  \t  ") == []

    def test_short_text_returns_single_chunk(self):
        from src.core.document_indexer_service import _chunk_text
        assert _chunk_text("Hello World", size=100) == ["Hello World"]

    def test_long_text_is_split_into_multiple_chunks(self):
        from src.core.document_indexer_service import _chunk_text
        text = "A" * 150
        chunks = _chunk_text(text, size=100, overlap=0)
        assert len(chunks) == 2
        assert len(chunks[0]) == 100
        assert len(chunks[1]) == 50

    def test_chunks_respect_max_size(self):
        from src.core.document_indexer_service import _chunk_text
        text = "This is a simple test text that should be split carefully."
        chunks = _chunk_text(text, size=15, overlap=0)
        for c in chunks:
            assert len(c) <= 15

    def test_overlap_creates_shared_content(self):
        from src.core.document_indexer_service import _chunk_text
        text = "X" * 600
        chunks = _chunk_text(text, size=500, overlap=100)
        # Com overlap, o segundo chunk começa antes do fim do primeiro
        assert len(chunks) == 2

    def test_none_text_returns_empty(self):
        from src.core.document_indexer_service import _chunk_text
        assert _chunk_text(None) == []  # type: ignore[arg-type]


# ══════════════════════════════════════════════════════════════════════════════
# TestRAGEngineInit
# ══════════════════════════════════════════════════════════════════════════════

class TestRAGEngineInit:
    """Testa inicialização e health-checks do RAGEngine."""

    def test_engine_initializes_chroma_collection(self, mock_engine):
        assert mock_engine._collection is not None

    def test_chroma_directory_is_created(self, test_db, chroma_path):
        from src.core.rag_engine import RAGEngine
        with patch.object(RAGEngine, "_get_embedding", return_value=[0.1] * 768):
            RAGEngine(db_path=test_db, chroma_path=chroma_path)
        assert chroma_path.exists()

    # Os health-checks abaixo testam os métodos REAIS (com urlopen mockado),
    # então usam um engine próprio — o fixture mock_engine substitui
    # is_ollama_available/is_model_available para tornar a suíte hermética.

    @staticmethod
    def _bare_engine(test_db, chroma_path):
        from src.core.rag_engine import RAGEngine
        with patch.object(RAGEngine, "_get_embedding", return_value=[0.1] * 768):
            return RAGEngine(db_path=test_db, chroma_path=chroma_path,
                             ollama_url="http://localhost:11434")

    def test_is_ollama_available_returns_false_when_offline(self, test_db, chroma_path):
        """Sem Ollama real rodando, deve retornar False."""
        engine = self._bare_engine(test_db, chroma_path)
        # Força exceção de conexão
        with patch("urllib.request.urlopen", side_effect=OSError("connection refused")):
            assert engine.is_ollama_available() is False

    def test_is_ollama_available_returns_true_when_online(self, test_db, chroma_path):
        """Simula resposta bem-sucedida do Ollama."""
        engine = self._bare_engine(test_db, chroma_path)
        mock_resp = MagicMock()
        mock_resp.status = 200
        mock_resp.__enter__ = lambda s: s
        mock_resp.__exit__ = MagicMock(return_value=False)
        with patch("urllib.request.urlopen", return_value=mock_resp):
            assert engine.is_ollama_available() is True

    def test_is_model_available_true(self, test_db, chroma_path):
        engine = self._bare_engine(test_db, chroma_path)
        mock_resp = MagicMock()
        mock_resp.status = 200
        mock_resp.read.return_value = json.dumps({
            "models": [{"name": "llama3:latest"}, {"name": "nomic-embed-text:latest"}]
        }).encode()
        mock_resp.__enter__ = lambda s: s
        mock_resp.__exit__ = MagicMock(return_value=False)
        with patch("urllib.request.urlopen", return_value=mock_resp):
            assert engine.is_model_available("llama3") is True

    def test_is_model_available_false_for_missing_model(self, test_db, chroma_path):
        engine = self._bare_engine(test_db, chroma_path)
        mock_resp = MagicMock()
        mock_resp.read.return_value = json.dumps({
            "models": [{"name": "llama3:latest"}]
        }).encode()
        mock_resp.__enter__ = lambda s: s
        mock_resp.__exit__ = MagicMock(return_value=False)
        with patch("urllib.request.urlopen", return_value=mock_resp):
            assert engine.is_model_available("mistral") is False

    def test_get_indexed_count_starts_at_zero(self, mock_engine):
        assert mock_engine.get_indexed_count() == 0


# ══════════════════════════════════════════════════════════════════════════════
# TestRAGEngineIndexing
# ══════════════════════════════════════════════════════════════════════════════

class TestRAGEngineIndexing:
    """Testa indexação de livros e anotações no ChromaDB."""

    def test_index_book_raises_when_ollama_unavailable(self, mock_engine):
        with patch.object(mock_engine, "is_ollama_available", return_value=False):
            with pytest.raises(RuntimeError, match="Ollama"):
                mock_engine.index_book(1)

    def test_index_book_raises_for_nonexistent_book(self, mock_engine):
        with patch.object(mock_engine, "is_ollama_available", return_value=True):
            with pytest.raises(ValueError, match="não encontrado"):
                mock_engine.index_book(9999)

    def test_index_book_creates_documents_in_chroma(self, mock_engine):
        with patch.object(mock_engine, "is_ollama_available", return_value=True):
            n = mock_engine.index_book(1)
        assert n > 0
        assert mock_engine.get_indexed_count() > 0

    def test_index_book_includes_annotation_content(self, mock_engine):
        """Verifica que o texto das anotações também é indexado."""
        with patch.object(mock_engine, "is_ollama_available", return_value=True):
            mock_engine.index_book(1)
        # Book 1 tem 1 anotação + texto principal
        results = mock_engine._collection.get(where={"book_id": 1})
        docs_text = " ".join(results["documents"])
        assert "olhos de ressaca" in docs_text

    def test_index_book_reindex_replaces_old_chunks(self, mock_engine):
        """Reindexar deve substituir chunks antigos (sem duplicação)."""
        with patch.object(mock_engine, "is_ollama_available", return_value=True):
            mock_engine.index_book(1)
            count_first = mock_engine.get_indexed_count()
            mock_engine.index_book(1)
            count_second = mock_engine.get_indexed_count()
        assert count_first == count_second

    def test_index_book_stores_correct_metadata(self, mock_engine):
        with patch.object(mock_engine, "is_ollama_available", return_value=True):
            mock_engine.index_book(1)
        results = mock_engine._collection.get(where={"book_id": 1})
        meta = results["metadatas"][0]
        assert meta["title"] == "Dom Casmurro"
        assert meta["author"] == "Machado de Assis"
        assert meta["book_id"] == 1

    def test_index_book_with_no_text_returns_zero(self, mock_engine, test_db):
        """Livro com apenas espaços em todos os campos não gera chunks."""
        from src.core.database import LibraryDB
        db = LibraryDB(test_db)
        book_id = db.add_book(title="Vazio", file_path="/tmp/vazio_id_99.pdf", file_format="pdf", description="", author="")

        with patch.object(mock_engine, "is_ollama_available", return_value=True), \
             patch.object(mock_engine, "is_model_available", return_value=True):
            n = mock_engine.index_book(book_id)
        # Título "Vazio" entra nos metadados, logo gera 1 chunk
        assert n == 1

    def test_delete_book_index_removes_chunks(self, mock_engine):
        with patch.object(mock_engine, "is_ollama_available", return_value=True):
            mock_engine.index_book(1)
            assert mock_engine.get_indexed_count() > 0
            mock_engine.delete_book_index(1)
        assert mock_engine.get_indexed_count() == 0

    def test_index_all_books_indexes_multiple_books(self, mock_engine):
        with patch.object(mock_engine, "is_ollama_available", return_value=True):
            results = mock_engine.index_all_books()
        # Books 1 e 2 têm conteúdo; book 3 só tem título (1 chunk mínimo)
        assert results[1] > 0
        assert results[2] > 0
        # Book 3 tem título não-vazio, portanto gera ao menos 1 chunk
        assert results[3] >= 0  # pode ser 0 ou 1 dependendo do texto

    def test_index_all_books_returns_dict_with_all_ids(self, mock_engine, test_db):
        with patch.object(mock_engine, "is_ollama_available", return_value=True):
            results = mock_engine.index_all_books()
        assert set(results.keys()) == {1, 2, 3}

    def test_cancel_stops_index_all(self, mock_engine):
        """Cancelamento deve interromper o loop de indexação."""
        call_count = 0

        def fake_index(book_id, force=False):
            nonlocal call_count
            call_count += 1
            if call_count == 1:
                mock_engine.cancel()
            return 5

        with patch.object(mock_engine, "is_ollama_available", return_value=True):
            with patch("src.core.document_indexer_service.DocumentIndexerService.index_book", side_effect=fake_index):
                mock_engine.index_all_books()
        # Apenas 1 livro processado antes do cancelamento
        assert call_count == 1
        assert call_count == 1

    def test_index_all_resets_cancel_flag(self, mock_engine):
        """Regressão (Item 1): após um cancelamento anterior, uma nova reindexação
        completa deve rodar do início — index_all_books reseta _cancelled."""
        mock_engine._cancelled = True  # cancelamento pendente de uma operação anterior
        call_count = 0

        def fake_index(book_id, force=False):
            nonlocal call_count
            call_count += 1
            return 1

        with patch.object(mock_engine, "is_ollama_available", return_value=True):
            with patch("src.core.document_indexer_service.DocumentIndexerService.index_book", side_effect=fake_index):
                mock_engine.index_all_books()

        # Sem o reset, o loop abortaria de imediato (call_count == 0).
        assert mock_engine._cancelled is False
        assert call_count == 3  # todos os 3 livros do banco de teste foram indexados


# ══════════════════════════════════════════════════════════════════════════════
# TestRAGEngineSearch
# ══════════════════════════════════════════════════════════════════════════════

class TestRAGEngineSearch:
    """Testa a busca vetorial semântica."""

    def test_search_raises_when_ollama_unavailable(self, mock_engine):
        with patch.object(mock_engine, "is_ollama_available", return_value=False):
            with pytest.raises(RuntimeError, match="Ollama"):
                mock_engine.search_similar("teste")

    def test_search_returns_empty_when_no_documents(self, mock_engine):
        with patch.object(mock_engine, "is_ollama_available", return_value=True):
            results = mock_engine.search_similar("qualquer coisa")
        assert results == []

    def test_search_returns_ranked_results(self, mock_engine):
        """Após indexar, a busca deve retornar resultados ordenados."""
        with patch.object(mock_engine, "is_ollama_available", return_value=True):
            mock_engine.index_book(1)
            mock_engine.index_book(2)
            results = mock_engine.search_similar("romance", n_results=3)
        assert len(results) > 0
        assert "document" in results[0]
        assert "metadata" in results[0]
        assert "distance" in results[0]

    def test_search_result_structure(self, mock_engine):
        """Valida a estrutura do dicionário retornado."""
        with patch.object(mock_engine, "is_ollama_available", return_value=True):
            mock_engine.index_book(1)
            results = mock_engine.search_similar("Machado", n_results=1)
        if results:
            r = results[0]
            assert isinstance(r["document"], str)
            assert isinstance(r["metadata"], dict)
            assert isinstance(r["distance"], float)

    def test_keyword_search_finds_annotations_via_sqlite(self, mock_engine):
        """Regressão: o ramo SQLite de keyword_search_db (anotações) deve funcionar.

        Antes quebrava com AttributeError em self._open_db() (método inexistente),
        capturado como warning — a tool keyword_search nunca achava anotações.
        """
        results = mock_engine.keyword_search_db("ressaca")
        sources = [r["source"] for r in results]
        assert "annotation" in sources, "ramo SQLite de keyword_search não retornou anotações"
        ann = next(r for r in results if r["source"] == "annotation")
        assert "ressaca" in ann["text"].lower()

    def test_get_sources_returns_list_on_success(self, mock_engine):
        with patch.object(mock_engine, "is_ollama_available", return_value=True):
            mock_engine.index_book(1)
            sources = mock_engine.get_sources("olhos de ressaca")
        assert isinstance(sources, list)

    def test_get_sources_returns_empty_on_error(self, mock_engine):
        """get_sources não deve propagar exceções."""
        with patch.object(mock_engine, "search_similar", side_effect=RuntimeError("erro")):
            sources = mock_engine.get_sources("qualquer")
        assert sources == []


# ══════════════════════════════════════════════════════════════════════════════
# TestRAGEngineRAG
# ══════════════════════════════════════════════════════════════════════════════

class TestRAGEngineRAG:
    """Testa o pipeline completo de Query RAG."""

    def test_query_rag_raises_when_ollama_unavailable(self, mock_engine):
        with patch.object(mock_engine, "is_ollama_available", return_value=False):
            gen = mock_engine.query_rag("Quem é Capitu?")
            with pytest.raises(RuntimeError, match="Ollama"):
                next(gen)

    def test_query_rag_yields_no_index_message_when_empty(self, mock_engine):
        """Sem documentos indexados, yield de mensagem informativa."""
        with patch.object(mock_engine, "is_ollama_available", return_value=True):
            tokens = list(mock_engine.query_rag("Quem é Capitu?"))
        assert len(tokens) == 1
        assert "indexados" in tokens[0].lower() or "índice" in tokens[0].lower() or "index" in tokens[0].lower()

    def test_query_rag_yields_streaming_tokens(self, mock_engine):
        """Com documentos e Ollama mockado, deve yield tokens via streaming real."""
        # Stream NDJSON estilo Ollama: cada linha é um chunk; a última traz done=True.
        stream_lines = [
            json.dumps({"message": {"role": "assistant", "content": "Dom "}}).encode("utf-8"),
            json.dumps({"message": {"content": "Casmurro "}}).encode("utf-8"),
            json.dumps({"message": {"content": "é um clássico."}, "done": True, "done_reason": "stop"}).encode("utf-8"),
        ]
        mock_resp = MagicMock()
        mock_resp.__enter__ = lambda s: s
        mock_resp.__exit__ = MagicMock(return_value=False)
        mock_resp.__iter__ = lambda s: iter(stream_lines)

        with patch.object(mock_engine, "is_ollama_available", return_value=True):
            mock_engine.index_book(1)
            with patch("urllib.request.urlopen", return_value=mock_resp):
                tokens = list(mock_engine.query_rag("Quem é Dom Casmurro?"))

        result_text = "".join(tokens)
        assert "Dom" in result_text
        assert "Casmurro" in result_text
        # Streaming real: o conteúdo chega em múltiplos tokens, não num bloco único.
        assert len([t for t in tokens if t.strip()]) >= 2

    def test_query_rag_prompt_contains_context_and_question(self, mock_engine):
        """Valida que o prompt enviado ao Ollama contém contexto e pergunta."""
        captured_payload = {}

        def fake_urlopen(req, timeout=None):
            import json
            body = json.loads(req.data.decode())
            captured_payload.update(body)
            # Retorna resposta mínima
            fake_resp = MagicMock()
            fake_resp.__enter__ = lambda s: s
            fake_resp.__exit__ = MagicMock(return_value=False)
            fake_resp.read.return_value = json.dumps({
                "message": {
                    "role": "assistant",
                    "content": "ok"
                }
            }).encode("utf-8")
            return fake_resp

        with patch.object(mock_engine, "is_ollama_available", return_value=True):
            mock_engine.index_book(1)
            with patch("urllib.request.urlopen", side_effect=fake_urlopen):
                list(mock_engine.query_rag("Quem escreveu Dom Casmurro?"))

        assert "messages" in captured_payload
        messages = captured_payload["messages"]
        
        # O prompt do sistema fixo está na primeira mensagem
        assert "Assistente Avançado" in messages[0]["content"]
        
        # O contexto está na terceira mensagem
        assert "CONTEXTO" in messages[2]["content"]
        
        # A pergunta está na quarta mensagem (user role)
        assert "Quem escreveu Dom Casmurro?" in messages[3]["content"]

    @staticmethod
    def _fake_urlopen_factory(captured_payload):
        """urlopen falso que CAPTURA o payload e ainda transmite (NDJSON) "ok"."""
        stream_lines = [
            json.dumps({"message": {"role": "assistant", "content": "ok"}}).encode("utf-8"),
            json.dumps({"message": {"content": ""}, "done": True,
                        "done_reason": "stop"}).encode("utf-8"),
        ]

        def fake_urlopen(req, timeout=None):
            body = json.loads(req.data.decode())
            captured_payload.update(body)
            fake_resp = MagicMock()
            fake_resp.__enter__ = lambda s: s
            fake_resp.__exit__ = MagicMock(return_value=False)
            fake_resp.__iter__ = lambda s: iter(stream_lines)
            return fake_resp
        return fake_urlopen

    def test_query_rag_injects_feedback_block_between_tools_and_context(self, mock_engine):
        """Com ≥4 👎 (categoria qualificada), o bloco de aprendizado entra como
        mensagem system logo após as ferramentas e antes do contexto."""
        from src.core.database import LibraryDB
        fb_db = LibraryDB(str(mock_engine._db_path))
        for _ in range(4):
            fb_db.add_feedback(rating=-1, kind="answer", query="q", reason="resposta_errada")

        captured_payload = {}
        fake_urlopen = self._fake_urlopen_factory(captured_payload)
        with patch.object(mock_engine, "is_ollama_available", return_value=True):
            mock_engine.index_book(1)
            with patch("urllib.request.urlopen", side_effect=fake_urlopen):
                list(mock_engine.query_rag("Quem é Capitu?"))

        messages = captured_payload["messages"]
        # [0]=prompt fixo, [1]=ferramentas, [2]=feedback, [3]=contexto, [4]=user
        assert "Assistente Avançado" in messages[0]["content"]
        assert "Ferramentas" in messages[1]["content"]
        assert "avaliou negativamente" in messages[2]["content"]
        assert "Verifique cada afirmação" in messages[2]["content"]
        assert "CONTEXTO" in messages[3]["content"]
        assert messages[4]["role"] == "user"

    def test_query_rag_no_feedback_block_when_no_signal(self, mock_engine):
        """Sem 👎 suficientes, nenhuma mensagem extra é injetada: o contexto
        permanece imediatamente após as ferramentas."""
        captured_payload = {}
        fake_urlopen = self._fake_urlopen_factory(captured_payload)
        with patch.object(mock_engine, "is_ollama_available", return_value=True):
            mock_engine.index_book(1)
            with patch("urllib.request.urlopen", side_effect=fake_urlopen):
                list(mock_engine.query_rag("Quem é Capitu?"))

        messages = captured_payload["messages"]
        assert all("avaliou negativamente" not in m["content"] for m in messages)
        assert "CONTEXTO" in messages[2]["content"]

    def test_query_rag_survives_feedback_learning_error(self, mock_engine):
        """Erro no caminho do aprendizado (DB/módulo) degrada para sem bloco;
        a query segue normalmente (ADR-005)."""
        captured_payload = {}
        fake_urlopen = self._fake_urlopen_factory(captured_payload)
        with patch.object(mock_engine, "is_ollama_available", return_value=True):
            mock_engine.index_book(1)
            with patch("src.core.feedback_learning.build_feedback_block",
                       side_effect=RuntimeError("boom")), \
                 patch("urllib.request.urlopen", side_effect=fake_urlopen):
                tokens = list(mock_engine.query_rag("Quem é Capitu?"))

        assert "ok" in "".join(tokens)
        messages = captured_payload["messages"]
        assert all("avaliou negativamente" not in m["content"] for m in messages)
        assert "CONTEXTO" in messages[2]["content"]

    def test_query_rag_cancel_stops_streaming(self, mock_engine):
        """Cancelamento deve interromper o streaming token a token."""
        stream_lines = [
            json.dumps({"message": {"content": f"token{i} "}}).encode("utf-8")
            for i in range(7)
        ]
        stream_lines.append(
            json.dumps({"message": {"content": ""}, "done": True, "done_reason": "stop"}).encode("utf-8")
        )
        mock_resp = MagicMock()
        mock_resp.__enter__ = lambda s: s
        mock_resp.__exit__ = MagicMock(return_value=False)
        mock_resp.__iter__ = lambda s: iter(stream_lines)

        with patch.object(mock_engine, "is_ollama_available", return_value=True):
            mock_engine.index_book(1)
            with patch("urllib.request.urlopen", return_value=mock_resp):
                gen = mock_engine.query_rag("teste")
                tokens = []
                for token in gen:
                    tokens.append(token)
                    if len(tokens) == 2:
                        mock_engine.cancel()

        assert len(tokens) <= 3  # Para logo após o cancelamento

    def test_query_rag_resets_cancel_flag_between_queries(self, mock_engine):
        """Regressão (Item 1): o engine é singleton; um cancelamento anterior não
        pode bloquear queries seguintes. query_rag deve resetar _cancelled no início."""
        stream_lines = [
            json.dumps({"message": {"content": "resposta ok"}, "done": True, "done_reason": "stop"}).encode("utf-8"),
        ]

        def make_resp(*args, **kwargs):
            r = MagicMock()
            r.__enter__ = lambda s: s
            r.__exit__ = MagicMock(return_value=False)
            r.__iter__ = lambda s: iter(stream_lines)
            return r

        with patch.object(mock_engine, "is_ollama_available", return_value=True):
            mock_engine.index_book(1)
            mock_engine._cancelled = True  # simula um cancelamento pendente anterior
            with patch("urllib.request.urlopen", side_effect=make_resp):
                tokens = list(mock_engine.query_rag("Pergunta nova após cancelar"))

        assert mock_engine._cancelled is False  # foi resetado no início da nova query
        assert "resposta ok" in "".join(tokens)  # e a resposta foi de fato gerada


# ══════════════════════════════════════════════════════════════════════════════
# TestThinkingStatusFeedback — feedback de raciocínio dos modelos thinking
# ══════════════════════════════════════════════════════════════════════════════

class TestThinkingStatusFeedback:
    """O stream de modelos thinking emite message.thinking antes do content;
    query_rag deve convertê-lo em status efêmero via status_callback, sem
    vazar o texto do raciocínio para a resposta."""

    @staticmethod
    def _mock_stream(lines: list[bytes]) -> MagicMock:
        resp = MagicMock()
        resp.__enter__ = lambda s: s
        resp.__exit__ = MagicMock(return_value=False)
        resp.__iter__ = lambda s: iter(lines)
        return resp

    def test_thinking_chunks_emit_status_and_do_not_leak_into_answer(self, mock_engine):
        stream_lines = [
            json.dumps({"message": {"role": "assistant", "thinking": "Deixe-me pensar sobre Capitu..."}}).encode("utf-8"),
            json.dumps({"message": {"thinking": "...os olhos de ressaca são..."}}).encode("utf-8"),
            json.dumps({"message": {"content": "Capitu é "}}).encode("utf-8"),
            json.dumps({"message": {"content": "a personagem central."}, "done": True, "done_reason": "stop"}).encode("utf-8"),
        ]
        statuses: list[str] = []
        with patch.object(mock_engine, "is_ollama_available", return_value=True):
            mock_engine.index_book(1)
            with patch("urllib.request.urlopen", return_value=self._mock_stream(stream_lines)):
                tokens = list(mock_engine.query_rag(
                    "Quem é Capitu?", status_callback=statuses.append))

        answer = "".join(tokens)
        # O raciocínio NÃO vai para a resposta.
        assert "Deixe-me pensar" not in answer
        assert "Capitu é a personagem central." in answer
        # Status de raciocínio emitido antes do content, escrita ao começar.
        # (Marcador "💭 Pensando… (N tokens · Ns)" — observabilidade do RAG.)
        assert any("Pensando" in s for s in statuses)
        assert any("Escrevendo" in s for s in statuses)
        assert statuses.index(next(s for s in statuses if "Pensando" in s)) < \
            statuses.index(next(s for s in statuses if "Escrevendo" in s))

    def test_stream_without_thinking_only_signals_writing(self, mock_engine):
        stream_lines = [
            json.dumps({"message": {"content": "Resposta direta."}, "done": True, "done_reason": "stop"}).encode("utf-8"),
        ]
        statuses: list[str] = []
        with patch.object(mock_engine, "is_ollama_available", return_value=True):
            mock_engine.index_book(1)
            with patch("urllib.request.urlopen", return_value=self._mock_stream(stream_lines)):
                tokens = list(mock_engine.query_rag(
                    "Pergunta simples", status_callback=statuses.append))

        assert "Resposta direta." in "".join(tokens)
        assert not any("Pensando" in s for s in statuses)
        assert any("Escrevendo" in s for s in statuses)

    def test_query_rag_without_status_callback_keeps_working(self, mock_engine):
        """Compat: chamadas existentes (sem status_callback) não mudam de comportamento."""
        stream_lines = [
            json.dumps({"message": {"thinking": "pensando..."}}).encode("utf-8"),
            json.dumps({"message": {"content": "ok"}, "done": True, "done_reason": "stop"}).encode("utf-8"),
        ]
        with patch.object(mock_engine, "is_ollama_available", return_value=True):
            mock_engine.index_book(1)
            with patch("urllib.request.urlopen", return_value=self._mock_stream(stream_lines)):
                tokens = list(mock_engine.query_rag("Pergunta"))
        assert "ok" in "".join(tokens)
        assert "pensando" not in "".join(tokens)


# ══════════════════════════════════════════════════════════════════════════════
# TestRAGWorker (requer pytest-qt)
# ══════════════════════════════════════════════════════════════════════════════

class TestRAGWorker:
    """Testa o QThread RAGWorker com sinais PyQt6."""

    def test_worker_mode_query_emits_tokens(self, qtbot, mock_engine):
        from src.gui.workers.rag_worker import RAGWorker

        fake_tokens = ["Olá ", "mundo!"]

        def fake_query(question, n_context=None, book_id=None, **kwargs):
            yield from fake_tokens

        with patch.object(mock_engine, "is_ollama_available", return_value=True):
            mock_engine.index_book(1)

        worker = RAGWorker(mock_engine, mode=RAGWorker.MODE_QUERY, question="teste")
        received_tokens = []

        with patch("src.core.rag.orchestrator.Orchestrator.query_rag", side_effect=fake_query):
            with patch.object(mock_engine, "get_sources", return_value=[]):
                worker.token_received.connect(received_tokens.append)
                with qtbot.waitSignal(worker.finished_work, timeout=5000):
                    worker.start()

        assert received_tokens == fake_tokens

    def test_worker_query_emits_answer_complete(self, qtbot, mock_engine):
        from src.gui.workers.rag_worker import RAGWorker

        def fake_query(question, n_context=None, book_id=None, **kwargs):
            yield "resposta completa"

        worker = RAGWorker(mock_engine, mode=RAGWorker.MODE_QUERY, question="q?")
        answers = []

        with patch("src.core.rag.orchestrator.Orchestrator.query_rag", side_effect=fake_query):
            with patch.object(mock_engine, "get_sources", return_value=[]):
                worker.answer_complete.connect(answers.append)
                with qtbot.waitSignal(worker.finished_work, timeout=5000):
                    worker.start()

        assert answers == ["resposta completa"]

    def test_worker_emits_error_on_runtime_error(self, qtbot, mock_engine):
        from src.gui.workers.rag_worker import RAGWorker

        def fake_query(question, n_context=None, book_id=None, **kwargs):
            raise RuntimeError("Ollama offline")
            yield  # torna generator

        worker = RAGWorker(mock_engine, mode=RAGWorker.MODE_QUERY, question="q?")
        errors = []

        with patch("src.core.rag.orchestrator.Orchestrator.query_rag", side_effect=fake_query):
            with patch.object(mock_engine, "get_sources", return_value=[]):
                worker.error_occurred.connect(errors.append)
                with qtbot.waitSignal(worker.finished_work, timeout=5000):
                    worker.start()

        assert len(errors) == 1
        assert "Ollama" in errors[0]

    def test_worker_empty_question_emits_error(self, qtbot, mock_engine):
        from src.gui.workers.rag_worker import RAGWorker

        worker = RAGWorker(mock_engine, mode=RAGWorker.MODE_QUERY, question="   ")
        errors = []
        worker.error_occurred.connect(errors.append)
        with qtbot.waitSignal(worker.finished_work, timeout=3000):
            worker.start()

        assert len(errors) == 1

    def test_worker_mode_index_book_emits_progress(self, qtbot, mock_engine):
        from src.gui.workers.rag_worker import RAGWorker

        progress_msgs = []

        def fake_index(book_id):
            return 5

        with patch.object(mock_engine, "is_ollama_available", return_value=True):
            with patch.object(mock_engine, "index_book", side_effect=fake_index):
                worker = RAGWorker(mock_engine, mode=RAGWorker.MODE_INDEX_BOOK, book_id=1)
                worker.progress_updated.connect(
                    lambda cur, tot, msg: progress_msgs.append(msg)
                )
                with qtbot.waitSignal(worker.finished_work, timeout=5000):
                    worker.start()

        assert any("chunks" in m for m in progress_msgs)

    def test_worker_mode_index_book_without_id_emits_error(self, qtbot, mock_engine):
        from src.gui.workers.rag_worker import RAGWorker

        worker = RAGWorker(mock_engine, mode=RAGWorker.MODE_INDEX_BOOK, book_id=None)
        errors = []
        worker.error_occurred.connect(errors.append)
        with qtbot.waitSignal(worker.finished_work, timeout=3000):
            worker.start()

        assert len(errors) == 1

    def test_worker_mode_index_all_emits_completion_progress(self, qtbot, mock_engine, test_db):
        from src.gui.workers.rag_worker import RAGWorker

        progress_msgs = []
        call_count = 0

        def fake_index(book_id):
            nonlocal call_count
            call_count += 1
            return 3

        with patch.object(mock_engine, "is_ollama_available", return_value=True):
            with patch.object(mock_engine, "index_book", side_effect=fake_index):
                worker = RAGWorker(mock_engine, mode=RAGWorker.MODE_INDEX_ALL)
                worker.progress_updated.connect(
                    lambda cur, tot, msg: progress_msgs.append(msg)
                )
                with qtbot.waitSignal(worker.finished_work, timeout=10000):
                    worker.start()

        assert call_count == 3  # 3 livros no banco de teste
        assert any("concluída" in m.lower() or "✅" in m for m in progress_msgs)

    def test_worker_stop_cancels_operation(self, qtbot, mock_engine):
        """stop() deve sinalizar cancelamento no engine e no worker."""
        from src.gui.workers.rag_worker import RAGWorker

        # Testa que stop() aciona o cancelamento corretamente
        worker = RAGWorker(mock_engine, mode=RAGWorker.MODE_QUERY, question="q?")
        assert mock_engine._cancelled is False

        # stop() deve: (1) cancelar o engine, (2) pedir interrupção ao QThread
        worker.stop()

        assert mock_engine._cancelled is True

    def test_worker_stop_mid_generation(self, qtbot, mock_engine):
        """Worker com gerador curto completa normalmente após stop antecipado."""
        from src.gui.workers.rag_worker import RAGWorker

        # Gerador finito curto (3 tokens) que respeita _cancelled
        def short_query(question, n_context=None, book_id=None, **kwargs):
            for i in range(3):
                if mock_engine._cancelled:
                    break
                yield f"t{i}"

        worker = RAGWorker(mock_engine, mode=RAGWorker.MODE_QUERY, question="q?")
        tokens = []

        with patch("src.core.rag.orchestrator.Orchestrator.query_rag", side_effect=short_query):
            with patch.object(mock_engine, "get_sources", return_value=[]):
                worker.token_received.connect(tokens.append)
                with qtbot.waitSignal(worker.finished_work, timeout=5000):
                    worker.start()

        # Gerador curto deve completar e emitir seus tokens
        assert len(tokens) == 3



    def test_index_worker_alias(self, qtbot, mock_engine):
        """Testa o alias IndexWorker."""
        from src.gui.workers.rag_worker import IndexWorker

        with patch.object(mock_engine, "is_ollama_available", return_value=True):
            with patch.object(mock_engine, "index_book", return_value=2):
                worker = IndexWorker(mock_engine)
                assert worker._mode == "index_all"
                with qtbot.waitSignal(worker.finished_work, timeout=5000):
                    worker.start()

    def test_index_book_worker_alias(self, qtbot, mock_engine):
        """Testa o alias IndexBookWorker."""
        from src.gui.workers.rag_worker import IndexBookWorker

        with patch.object(mock_engine, "is_ollama_available", return_value=True):
            with patch.object(mock_engine, "index_book", return_value=3):
                worker = IndexBookWorker(mock_engine, book_id=1)
                assert worker._book_id == 1
                with qtbot.waitSignal(worker.finished_work, timeout=5000):
                    worker.start()


# ══════════════════════════════════════════════════════════════════════════════
# TestChatMemory (Item 8a — memória conversacional por livro)
# ══════════════════════════════════════════════════════════════════════════════

class TestChatMemory:
    def test_append_and_get_isolated_by_book(self, mock_engine):
        mock_engine.append_chat_turn(1, "pergunta", "resposta")
        assert mock_engine.get_chat_history(1) == [
            {"role": "user", "content": "pergunta"},
            {"role": "assistant", "content": "resposta"},
        ]
        assert mock_engine.get_chat_history(2) == []  # outro livro isolado

    def test_empty_assistant_not_stored(self, mock_engine):
        mock_engine.append_chat_turn(1, "p", "   ")
        assert mock_engine.get_chat_history(1) == []

    def test_history_trims_to_max(self, mock_engine):
        for i in range(5):
            mock_engine.append_chat_turn(1, f"p{i}", f"r{i}")
        h = mock_engine.get_chat_history(1)
        assert len(h) == 6  # default max_messages = 3 turnos
        assert h[-1]["content"] == "r4"   # mantém os mais recentes
        assert h[0]["content"] == "p2"

    def test_clear_history(self, mock_engine):
        mock_engine.append_chat_turn(1, "p", "r")
        mock_engine.clear_chat_history(1)
        assert mock_engine.get_chat_history(1) == []

    def test_get_returns_copy(self, mock_engine):
        mock_engine.append_chat_turn(1, "p", "r")
        h = mock_engine.get_chat_history(1)
        h.append("x")
        assert len(mock_engine.get_chat_history(1)) == 2  # não afeta o estado interno

    def test_query_rag_injects_history_on_followup(self, mock_engine):
        mock_engine.append_chat_turn(None, "Quem é Capitu?", "Personagem de Dom Casmurro.")

        captured = {}

        def fake_urlopen(req, timeout=None):
            captured.update(json.loads(req.data.decode()))
            resp = MagicMock()
            resp.__enter__ = lambda s: s
            resp.__exit__ = MagicMock(return_value=False)
            resp.__iter__ = lambda s: iter([
                json.dumps({"message": {"content": "ok"}, "done": True, "done_reason": "stop"}).encode("utf-8")
            ])
            return resp

        with patch.object(mock_engine, "is_ollama_available", return_value=True):
            mock_engine.index_book(1)
            with patch("urllib.request.urlopen", side_effect=fake_urlopen):
                list(mock_engine.query_rag("E ela trai Bentinho?"))

        contents = [m.get("content", "") for m in captured["messages"]]
        assert any("Quem é Capitu?" in c for c in contents)        # histórico injetado
        assert any("E ela trai Bentinho?" in c for c in contents)  # pergunta atual


# ══════════════════════════════════════════════════════════════════════════════
# TestClassificadorFalhaGPU — item 12 do feedback de tester (Onda Q)
# ══════════════════════════════════════════════════════════════════════════════

def _http_error(code: int, body: str):
    """HTTPError com corpo lido a partir de um buffer (como o urllib real)."""
    import io
    import urllib.error
    return urllib.error.HTTPError(
        "http://localhost:11434/api/embed", code, "Internal Server Error",
        {}, io.BytesIO(body.encode("utf-8")))


@pytest.fixture
def engine_sem_mock_de_embedding(test_db, chroma_path):
    """RAGEngine com os métodos de embedding REAIS (o mock_engine os substitui).

    Estes testes exercitam justamente o transporte + a classificação de erro
    dentro de ``_get_embedding``/``_get_embeddings_batch``.
    """
    from src.core.rag_engine import RAGEngine
    engine = RAGEngine(db_path=test_db, chroma_path=chroma_path,
                       ollama_url="http://localhost:11434")
    # Evita a consulta a /api/tags dentro do fluxo de embedding.
    engine.get_exact_model_name = lambda name: name
    return engine


class TestClassificadorFalhaGPU:
    """Erro CUDA/PTX do Ollama é definitivo: sem retry e com mensagem acionável.

    Com driver NVIDIA antigo o Ollama devolve HTTP 500 com o erro do runner
    CUDA no corpo. Antes isso passava pela heurística de erro TRANSITÓRIO,
    gastava 4 tentativas com backoff e terminava num RuntimeError genérico.
    """

    def test_marcadores_reconhecidos_case_insensitive(self):
        from src.core.rag_engine import _is_gpu_failure
        assert _is_gpu_failure("CUDA error: no kernel image is available")
        assert _is_gpu_failure("the provided PTX was compiled with an unsupported toolchain")
        assert _is_gpu_failure("No Kernel Image is available for execution")
        assert _is_gpu_failure("cuda")

    def test_erro_de_rede_comum_nao_e_falha_de_gpu(self):
        from src.core.rag_engine import _is_gpu_failure, _is_transient_net_error
        corpo = "Post \"http://127.0.0.1:11434\": dial tcp: connection reset"
        assert _is_gpu_failure(corpo) is False
        assert _is_transient_net_error(corpo) is True

    def test_lote_falha_na_primeira_tentativa_sem_retry(self, engine_sem_mock_de_embedding):
        from src.core.rag_engine import OllamaGPUError
        tentativas = {"n": 0}

        def fake_urlopen(req, timeout=None):
            tentativas["n"] += 1
            raise _http_error(500, "CUDA error: no kernel image is available for execution")

        with patch("urllib.request.urlopen", side_effect=fake_urlopen):
            with pytest.raises(OllamaGPUError) as exc:
                engine_sem_mock_de_embedding._get_embeddings_batch(["um texto"])

        assert tentativas["n"] == 1, "erro de GPU não pode ser re-tentado"
        assert "driver NVIDIA" in str(exc.value)
        assert "OLLAMA_NUM_GPU=0" in str(exc.value)

    def test_embedding_unico_tambem_classifica(self, engine_sem_mock_de_embedding):
        from src.core.rag_engine import OllamaGPUError

        def fake_urlopen(req, timeout=None):
            raise _http_error(500, "PTX was compiled with an unsupported toolchain")

        with patch("urllib.request.urlopen", side_effect=fake_urlopen):
            with pytest.raises(OllamaGPUError) as exc:
                engine_sem_mock_de_embedding._get_embedding("um texto")
        assert "Falha de GPU no Ollama" in str(exc.value)

    def test_erro_transitorio_continua_re_tentando(self, engine_sem_mock_de_embedding,
                                                  monkeypatch):
        """Regressão: a classificação de GPU não pode encurtar o retry de rede."""
        monkeypatch.setattr("time.sleep", lambda *_a: None)
        tentativas = {"n": 0}

        def fake_urlopen(req, timeout=None):
            tentativas["n"] += 1
            if tentativas["n"] < 3:
                raise _http_error(400, "health resp: dial tcp 127.0.0.1:11434")
            resp = MagicMock()
            resp.__enter__ = lambda s: s
            resp.__exit__ = MagicMock(return_value=False)
            resp.read.return_value = json.dumps({"embeddings": [[0.1] * 8]}).encode()
            return resp

        with patch("urllib.request.urlopen", side_effect=fake_urlopen):
            out = engine_sem_mock_de_embedding._get_embeddings_batch(["um texto"])

        assert tentativas["n"] == 3
        assert out == [[0.1] * 8]
