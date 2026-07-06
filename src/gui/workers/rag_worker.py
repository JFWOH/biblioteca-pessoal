"""QThread freeze-free para operações do pipeline RAG.

Seguindo as novas diretrizes do orquestrador resiliente e tolerante a falhas (ADR-006).
- Herda de QThread
- Roda de forma headless/freeze-free
- Comunicação com a GUI exclusivamente por pyqtSignal
"""

from __future__ import annotations

from typing import Any
from PyQt6.QtCore import QThread, pyqtSignal

from src.core.rag.orchestrator import Orchestrator


class RAGWorker(QThread):
    """Worker assíncrono para consultas RAG e indexação da biblioteca.

    Garante que a interface PyQt6 permaneça responsiva enquanto o LLM
    gera respostas ou a biblioteca é reindexada.

    Signals:
        token_received: Emitido a cada token gerado pelo LLM (streaming).
        status_updated: Estado efêmero da geração (raciocínio do modelo
            thinking, início da escrita) — não faz parte da resposta.
        answer_complete: Emitido com a resposta final completa.
        sources_found: Emitido com a lista de fontes usadas como contexto.
        progress_updated: (current, total, message) durante indexação.
        error_occurred: Emitido com mensagem de erro legível.
        finished_work: Emitido ao final, independente de sucesso ou falha.
    """

    token_received = pyqtSignal(str)
    status_updated = pyqtSignal(str)
    answer_complete = pyqtSignal(str)
    sources_found = pyqtSignal(list)
    progress_updated = pyqtSignal(int, int, str)   # current, total, msg
    error_occurred = pyqtSignal(str)
    file_not_found = pyqtSignal(int)               # book_id com arquivo ausente
    ui_mutation_requested = pyqtSignal(str, dict)   # action_type, data
    finished_work = pyqtSignal()

    # Modos de operação
    MODE_QUERY = "query"
    MODE_INDEX_BOOK = "index_book"
    MODE_INDEX_ALL = "index_all"

    def __init__(
        self,
        engine: Any,
        mode: str = MODE_QUERY,
        question: str = "",
        book_id: int | None = None,
        parent=None,
    ) -> None:
        super().__init__(parent)
        # Compatibilidade elegante com instâncias legadas de RAGEngine
        if isinstance(engine, Orchestrator):
            self._orchestrator = engine
            self._engine = engine.engine
        else:
            self._orchestrator = Orchestrator(engine)
            self._engine = engine
            
        self._mode = mode
        self._question = question
        self._book_id = book_id

    # ── Execução ───────────────────────────────────────────────────────────────

    def run(self) -> None:
        """Ponto de entrada da thread — nunca chamar diretamente."""
        try:
            if self._mode == self.MODE_QUERY:
                self._run_query()
            elif self._mode == self.MODE_INDEX_BOOK:
                self._run_index_book()
            elif self._mode == self.MODE_INDEX_ALL:
                self._run_index_all()
        except Exception as exc:
            self.error_occurred.emit(str(exc))
        finally:
            self.finished_work.emit()

    def _run_query(self) -> None:
        """Executa a consulta RAG com streaming de tokens via Orchestrator."""
        if not self._question.strip():
            self.error_occurred.emit("A pergunta não pode estar vazia.")
            return

        # Busca as fontes antes da geração e emite
        try:
            sources = self._engine.get_sources(self._question, book_id=self._book_id)
            self.sources_found.emit(sources)
        except Exception:
            pass  # Fontes são opcionais, não interrompemos a geração


        # Geração de streaming com controle de rounds e AgentState
        full_answer: list[str] = []
        
        generator = self._orchestrator.query_rag(
            self._question,
            book_id=self._book_id,
            ui_mutation_callback=self._emit_ui_mutation,
            status_callback=self._emit_status,
        )

        for token in generator:
            if self.isInterruptionRequested():
                self._engine.cancel()
                break
            # Emite os tokens de texto comum para o painel de chat
            self.token_received.emit(token)
            full_answer.append(token)

        self.answer_complete.emit("".join(full_answer))

    def _emit_ui_mutation(self, action_type: str, data: dict) -> None:
        """Callback thread-safe: emite sinal para a Main Thread processar a mutação visual."""
        self.ui_mutation_requested.emit(action_type, data)

    def _emit_status(self, status: str) -> None:
        """Callback thread-safe: repassa o estado efêmero da geração à GUI."""
        self.status_updated.emit(status)

    def _run_index_book(self) -> None:
        """Indexa um único livro com tratamento robusto de erros."""
        self._engine.reset_cancel()
        if self._book_id is None:
            self.error_occurred.emit("book_id não fornecido para indexação.")
            return
        self.progress_updated.emit(0, 1, "Indexando livro…")
        try:
            n = self._engine.index_book(self._book_id)
            self.progress_updated.emit(1, 1, f"✅ {n} chunks indexados.")
        except FileNotFoundError:
            self.file_not_found.emit(self._book_id)
            self.error_occurred.emit(
                f"⚠️ Arquivo não encontrado — livro {self._book_id} ignorado na indexação."
            )
        except Exception as exc:
            import traceback
            print(
                f"[RAGWorker][ERROR] Indexação do livro {self._book_id} falhou: {exc}",
                flush=True,
            )
            traceback.print_exc()
            self.error_occurred.emit(f"Erro ao indexar livro {self._book_id}: {exc}")

    def _run_index_all(self) -> None:
        """Reindexação completa da biblioteca com progresso e contagem de skips."""
        self._engine.reset_cancel()
        import sqlite3
        conn = sqlite3.connect(str(self._engine._db_path))
        try:
            total = conn.execute("SELECT COUNT(*) FROM books").fetchone()[0]
            book_ids = [r[0] for r in conn.execute("SELECT id FROM books").fetchall()]
        finally:
            conn.close()

        if total == 0:
            self.progress_updated.emit(0, 0, "Nenhum livro para indexar.")
            return

        # Migração de modelo de embeddings: se a collection foi construída com outro
        # modelo, a dimensão dos vetores mudou — recria a collection antes do loop.
        # Depois disso, index_book(force=False) reindexa tudo (has_book_indexed=False).
        try:
            if self._engine.needs_reindex():
                self.progress_updated.emit(0, total, "Modelo de embeddings atualizado — recriando índice…")
                self._engine.reset_collection()
        except Exception as exc:
            print(f"[RAGWorker] Falha ao recriar collection na migração: {exc}", flush=True)

        total_chunks = 0
        skipped: list[int] = []

        for i, book_id in enumerate(book_ids):
            if self.isInterruptionRequested():
                self._engine.cancel()
                break
            self.progress_updated.emit(i, total, f"Indexando livro {i + 1}/{total}…")
            try:
                n = self._engine.index_book(book_id)
                total_chunks += max(n, 0)
            except FileNotFoundError:
                skipped.append(book_id)
                self.file_not_found.emit(book_id)
            except TimeoutError as exc:
                import traceback
                print(f"[RAGWorker][TIMEOUT] Livro {book_id}: {exc}", flush=True)
                self.error_occurred.emit(f"⏳ Tempo esgotado (Timeout) ao indexar o livro {book_id}. Pulando...")
                skipped.append(book_id)
                continue
            except Exception as exc:
                import traceback
                print(
                    f"[RAGWorker][ERROR] Livro {book_id} falhou durante indexação: {exc}",
                    flush=True,
                )
                traceback.print_exc()
                self.error_occurred.emit(f"⚠️ Erro ao indexar o livro {book_id}: {exc}. Pulando para o próximo...")
                skipped.append(book_id)
                continue

        skip_msg = f" ({len(skipped)} ignorados — arquivo ausente)" if skipped else ""
        self.progress_updated.emit(
            total, total,
            f"✅ Indexação concluída — {total_chunks} chunks de {total} livros{skip_msg}."
        )

    # ── Controle ───────────────────────────────────────────────────────────────

    def stop(self) -> None:
        """Para a operação em andamento de forma graciosa."""
        self._engine.cancel()
        self.requestInterruption()


class IndexWorker(RAGWorker):
    """Alias semântico para workers de indexação da biblioteca completa."""

    def __init__(self, engine: Any, parent=None) -> None:
        super().__init__(engine, mode=RAGWorker.MODE_INDEX_ALL, parent=parent)


class IndexBookWorker(RAGWorker):
    """Alias semântico para worker de indexação de um único livro."""

    def __init__(self, engine: Any, book_id: int, parent=None) -> None:
        super().__init__(engine, mode=RAGWorker.MODE_INDEX_BOOK,
                         book_id=book_id, parent=parent)
