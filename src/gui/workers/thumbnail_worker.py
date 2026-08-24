"""Worker das miniaturas do sumário — renderiza fora da thread da GUI.

Onda P (rodada UX ago/2026). Antes, ``TOCWidget.load_toc`` renderizava até 40
miniaturas EM SÉRIE na thread de interface: ~1,2s de janela congelada em PDFs
grandes (88% do custo de abrir o livro, medido em
``tools/perf/measure_pdf_open.py``). Agora o sumário aparece na hora e cada
miniatura chega por sinal, conforme fica pronta.

Padrão do repo (``AutoIndexWorker``/``GraphWorker``): QThread com cancelamento
cooperativo. A renderização vive no leitor puro (``src/readers/**``) e o cache
em ``src/core/thumbnail_cache.py`` (ADR-006) — aqui só há orquestração.

Cada worker abre o SEU PRÓPRIO leitor: o documento PyMuPDF que a GUI usa para
exibir páginas não é thread-safe e não pode ser compartilhado entre threads.
"""

import logging

from PyQt6.QtCore import QThread, pyqtSignal

from src.core.thumbnail_cache import ThumbnailCache

logger = logging.getLogger(__name__)


class ThumbnailWorker(QThread):
    """Produz as miniaturas de uma lista de páginas, uma a uma."""

    thumbnail_ready = pyqtSignal(int, bytes)  # (página, PNG)
    finished_batch = pyqtSignal(int)          # quantas miniaturas entregou

    def __init__(self, filepath: str, pages, width: int = 110,
                 cache: ThumbnailCache | None = None, provider=None,
                 parent=None):
        """``provider``: callable(page, width) -> bytes PNG | None.

        Quando ``None`` (uso real), o worker abre o próprio leitor a partir de
        ``filepath``. Injetar um provider serve aos testes e a chamadores que já
        tenham um renderizador dedicado.
        """
        super().__init__(parent)
        self._filepath = str(filepath)
        # dict.fromkeys: remove páginas repetidas preservando a ordem do sumário
        # (a ordem visual é a que importa — as primeiras miniaturas são as que o
        # usuário vê primeiro).
        self._pages = list(dict.fromkeys(int(p) for p in pages))
        self._width = int(width)
        self._cache = cache if cache is not None else ThumbnailCache()
        self._provider = provider
        self._cancelled = False

    def cancel(self) -> None:
        """Cancelamento cooperativo: para no limite da próxima página."""
        self._cancelled = True

    @property
    def cancelled(self) -> bool:
        return self._cancelled

    def start(self, priority: QThread.Priority = QThread.Priority.LowPriority) -> None:
        """Miniatura é enfeite: nunca compete por CPU com a UI ou com o TTS."""
        super().start(priority)

    # ── Execução ──────────────────────────────────────────────────────

    def _abre_leitor(self):
        try:
            from src.readers.reader_factory import create_reader
            leitor = create_reader(self._filepath)
            leitor.open()
            return leitor
        except Exception as exc:  # ADR-005: sem miniatura é degradação aceitável
            logger.warning("ThumbnailWorker: falha ao abrir '%s': %s",
                           self._filepath, exc)
            return None

    def run(self):
        entregues = 0
        leitor = None
        try:
            for page in self._pages:
                if self._cancelled:
                    break

                png = self._cache.get(self._filepath, page, self._width)
                if png is None:
                    render = self._provider
                    if render is None:
                        # Abertura preguiçosa: reabrir um livro cujas miniaturas
                        # estão todas em cache não abre leitor nenhum.
                        if leitor is None:
                            leitor = self._abre_leitor()
                            if leitor is None:
                                break
                        render = leitor.render_thumbnail
                    try:
                        png = render(page, self._width)
                    except Exception:
                        logger.debug("ThumbnailWorker: página %s falhou",
                                     page, exc_info=True)
                        png = None
                    if png:
                        self._cache.put(self._filepath, page, self._width, png)

                if png and not self._cancelled:
                    self.thumbnail_ready.emit(page, bytes(png))
                    entregues += 1
        except Exception as exc:  # ADR-005: nunca derrubar o app
            logger.warning("ThumbnailWorker falhou (%s): %s", self._filepath, exc)
        finally:
            if leitor is not None:
                try:
                    leitor.close()
                except Exception:
                    logger.debug("ThumbnailWorker: falha ao fechar leitor",
                                 exc_info=True)
            try:
                self._cache.prune()
            except Exception:
                logger.debug("ThumbnailWorker: poda do cache falhou",
                             exc_info=True)
            if not self._cancelled:
                self.finished_batch.emit(entregues)
