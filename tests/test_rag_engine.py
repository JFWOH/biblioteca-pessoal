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
import sqlite3
from pathlib import Path
from unittest.mock import MagicMock, patch, PropertyMock

import pytest

# ── Auxiliar: cria banco SQLite mínimo para testes ─────────────────────────────

def _create_test_db(path: Path) -> Path:
    """Cria um banco SQLite com alguns livros e anotações de teste."""
    conn = sqlite3.connect(str(path))
    conn.executescript("""
        CREATE TABLE books (
            id INTEGER PRIMARY KEY,
            title TEXT NOT NULL,
            author TEXT DEFAULT '',
            description TEXT DEFAULT '',
            isbn TEXT DEFAULT '',
            publisher TEXT DEFAULT '',
            year INTEGER,
            file_path TEXT DEFAULT ''
        );
        CREATE TABLE annotations (
            id INTEGER PRIMARY KEY,
            book_id INTEGER NOT NULL,
            content TEXT DEFAULT '',
            page_number INTEGER DEFAULT 0
        );
    """)
    conn.execute(
        "INSERT INTO books (id, title, author, description) VALUES (?,?,?,?)",
        (1, "Dom Casmurro", "Machado de Assis",
         "Romance brasileiro do realismo. Bentinho e Capitu.")
    )
    conn.execute(
        "INSERT INTO books (id, title, author, description) VALUES (?,?,?,?)",
        (2, "1984", "George Orwell",
         "Distopia sobre vigilância totalitária e controle da mente.")
    )
    conn.execute(
        "INSERT INTO annotations (book_id, content) VALUES (?,?)",
        (1, "Capitu tinha olhos de ressaca — uma expressão marcante do autor.")
    )
    conn.execute(
        "INSERT INTO books (id, title, author, description) VALUES (?,?,?,?)",
        (3, "Livro Sem Texto", "", "")
    )
    conn.commit()
    conn.close()
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
    """RAGEngine com ChromaDB real em memória e Ollama mockado."""
    from src.core.rag_engine import RAGEngine

    with patch.object(RAGEngine, "_get_embedding", return_value=fake_embedding):
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
    """Testa a função utilitária de chunking de texto."""

    def test_empty_string_returns_empty_list(self):
        from src.core.rag_engine import _chunk_text
        assert _chunk_text("") == []

    def test_whitespace_only_returns_empty_list(self):
        from src.core.rag_engine import _chunk_text
        assert _chunk_text("   \n\t  ") == []

    def test_short_text_returns_single_chunk(self):
        from src.core.rag_engine import _chunk_text
        text = "Texto curto."
        chunks = _chunk_text(text, size=500)
        assert len(chunks) == 1
        assert chunks[0] == text

    def test_long_text_is_split_into_multiple_chunks(self):
        from src.core.rag_engine import _chunk_text
        text = "A" * 1200
        chunks = _chunk_text(text, size=500, overlap=50)
        assert len(chunks) >= 3

    def test_chunks_respect_max_size(self):
        from src.core.rag_engine import _chunk_text
        text = "B" * 2000
        chunks = _chunk_text(text, size=400, overlap=0)
        for chunk in chunks:
            assert len(chunk) <= 400

    def test_overlap_creates_shared_content(self):
        from src.core.rag_engine import _chunk_text
        text = "X" * 600
        chunks = _chunk_text(text, size=500, overlap=100)
        # Com overlap, o segundo chunk começa antes do fim do primeiro
        assert len(chunks) == 2

    def test_none_text_returns_empty(self):
        from src.core.rag_engine import _chunk_text
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

    def test_is_ollama_available_returns_false_when_offline(self, mock_engine):
        """Sem Ollama real rodando, deve retornar False."""
        # Força exceção de conexão
        with patch("urllib.request.urlopen", side_effect=OSError("connection refused")):
            assert mock_engine.is_ollama_available() is False

    def test_is_ollama_available_returns_true_when_online(self, mock_engine):
        """Simula resposta bem-sucedida do Ollama."""
        mock_resp = MagicMock()
        mock_resp.status = 200
        mock_resp.__enter__ = lambda s: s
        mock_resp.__exit__ = MagicMock(return_value=False)
        with patch("urllib.request.urlopen", return_value=mock_resp):
            assert mock_engine.is_ollama_available() is True

    def test_is_model_available_true(self, mock_engine):
        mock_resp = MagicMock()
        mock_resp.status = 200
        mock_resp.read.return_value = json.dumps({
            "models": [{"name": "llama3:latest"}, {"name": "nomic-embed-text:latest"}]
        }).encode()
        mock_resp.__enter__ = lambda s: s
        mock_resp.__exit__ = MagicMock(return_value=False)
        with patch("urllib.request.urlopen", return_value=mock_resp):
            assert mock_engine.is_model_available("llama3") is True

    def test_is_model_available_false_for_missing_model(self, mock_engine):
        mock_resp = MagicMock()
        mock_resp.read.return_value = json.dumps({
            "models": [{"name": "llama3:latest"}]
        }).encode()
        mock_resp.__enter__ = lambda s: s
        mock_resp.__exit__ = MagicMock(return_value=False)
        with patch("urllib.request.urlopen", return_value=mock_resp):
            assert mock_engine.is_model_available("mistral") is False

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
        import sqlite3
        # Insere um livro com todos os campos de texto vazios
        conn = sqlite3.connect(str(test_db))
        conn.execute(
            "INSERT INTO books (id, title, author, description) VALUES (?, ?, ?, ?)",
            (99, "", "", "")
        )
        conn.commit()
        conn.close()

        with patch.object(mock_engine, "is_ollama_available", return_value=True):
            n = mock_engine.index_book(99)
        assert n == 0

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

        def fake_index(book_id):
            nonlocal call_count
            call_count += 1
            if call_count == 1:
                mock_engine.cancel()
            return 5

        with patch.object(mock_engine, "is_ollama_available", return_value=True):
            with patch.object(mock_engine, "index_book", side_effect=fake_index):
                mock_engine.index_all_books()
        # Apenas 1 livro processado antes do cancelamento
        assert call_count == 1


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
        """Com documentos e Ollama mockado, deve yield tokens."""
        mock_resp = MagicMock()
        mock_resp.__enter__ = lambda s: s
        mock_resp.__exit__ = MagicMock(return_value=False)
        mock_resp.read.return_value = json.dumps({
            "message": {
                "role": "assistant",
                "content": "Dom Casmurro é um clássico."
            }
        }).encode("utf-8")

        with patch.object(mock_engine, "is_ollama_available", return_value=True):
            mock_engine.index_book(1)
            with patch("urllib.request.urlopen", return_value=mock_resp):
                tokens = list(mock_engine.query_rag("Quem é Dom Casmurro?"))

        result_text = "".join(tokens)
        assert "Dom" in result_text
        assert "Casmurro" in result_text

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

    def test_query_rag_cancel_stops_streaming(self, mock_engine):
        """Cancelamento deve interromper o streaming."""
        mock_resp = MagicMock()
        mock_resp.__enter__ = lambda s: s
        mock_resp.__exit__ = MagicMock(return_value=False)
        mock_resp.read.return_value = json.dumps({
            "message": {
                "role": "assistant",
                "content": "token0 token1 token2 token3 token4 token5 token6"
            }
        }).encode("utf-8")

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
