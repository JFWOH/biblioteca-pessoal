"""Diálogo do Dossiê do Livro (Fase 4 — roadmap memória/grafo).

Visão rica, por livro, do que o grafo já sabe: mapa conceitual, livros
relacionados, confiança por cobertura, anotações e síntese em texto via LLM.
Só LÊ dados já ingeridos (GraphStore/LibraryDB) — nunca dispara ingestão.
A síntese chega em background; sem Ollama o resto do dossiê segue de pé
(ADR-005).
"""

from PyQt6.QtWidgets import (
    QDialog, QVBoxLayout, QHBoxLayout, QLabel, QPushButton,
    QScrollArea, QSizePolicy, QWidget, QFrame,
)
from PyQt6.QtCore import Qt, pyqtSignal
from PyQt6.QtGui import QPixmap

from src.core.book_dossier import (
    build_dossier_data,
    build_dossier_synthesis_prompt,
    format_coverage_label,
    get_cached_synthesis,
    save_synthesis_cache,
)
from src.core.graph.graph_store import GraphStore
from src.gui.widgets.ai_response_card import AIResponseCard

_HEADER_STYLE = "dossierSectionHeader"
_BODY_STYLE = "dossierBody"


class BookDossierDialog(QDialog):
    """Dossiê do livro: dados instantâneos + síntese LLM assíncrona."""

    open_book_requested = pyqtSignal(int)  # clique em livro relacionado

    def __init__(self, db, book_id: int,
                 ollama_url: str = "http://localhost:11434",
                 model: str | None = None, parent=None):
        super().__init__(parent)
        self._db = db
        self._book_id = book_id
        self._ollama_url = ollama_url
        self._model = model
        self._worker = None
        self._synthesis_card: AIResponseCard | None = None

        self.setWindowTitle("📋 Dossiê do Livro")
        self.resize(560, 680)
        self.setObjectName("bookDossierDialog")

        self._data = build_dossier_data(db, GraphStore(db), book_id)
        self._setup_ui()
        self._start_synthesis()

    # ── UI ────────────────────────────────────────────────────────────

    def _setup_ui(self):
        root = QVBoxLayout(self)
        root.setContentsMargins(16, 16, 16, 16)
        root.setSpacing(12)

        scroll = QScrollArea()
        scroll.setWidgetResizable(True)
        # Conteúdo se adapta à largura do diálogo — nunca scroll horizontal.
        scroll.setHorizontalScrollBarPolicy(Qt.ScrollBarPolicy.ScrollBarAlwaysOff)
        scroll.setObjectName("dossierScroll")
        content = QWidget()
        content.setObjectName("dossierContent")
        lay = QVBoxLayout(content)
        lay.setContentsMargins(0, 0, 8, 0)
        lay.setSpacing(12)

        if self._data is None:
            lay.addWidget(self._label("Livro não encontrado.", _BODY_STYLE))
            lay.addStretch()
        else:
            self._build_header(lay)
            if self._data["concepts"]:
                self._build_synthesis(lay)
                self._build_concepts(lay)
                self._build_related(lay)
                self._build_confidence(lay)
            else:
                lay.addWidget(self._card(
                    "🌱 Este livro ainda não foi processado pelo grafo — "
                    "continue lendo que ele entra sozinho."))
            self._build_annotations(lay)
            lay.addStretch()

        scroll.setWidget(content)
        root.addWidget(scroll)

        close_btn = QPushButton("Fechar")
        close_btn.setObjectName("secondaryBtn")
        close_btn.setCursor(Qt.CursorShape.PointingHandCursor)
        close_btn.clicked.connect(self.accept)
        root.addWidget(close_btn)

    def _label(self, text: str, object_name: str) -> QLabel:
        lbl = QLabel(text)
        lbl.setWordWrap(True)
        lbl.setObjectName(object_name)
        return lbl

    def _card(self, text: str) -> QFrame:
        frame = QFrame()
        frame.setObjectName("dossierCard")
        lay = QVBoxLayout(frame)
        lay.setContentsMargins(12, 10, 12, 10)
        lay.addWidget(self._label(text, _BODY_STYLE))
        return frame

    def _build_header(self, lay: QVBoxLayout):
        book = self._data["book"]
        row = QHBoxLayout()
        row.setSpacing(12)
        cover = QLabel()
        cover.setFixedSize(72, 100)
        cover.setAlignment(Qt.AlignmentFlag.AlignCenter)
        cover.setObjectName("dossierCover")
        pixmap = QPixmap(book.get("cover_path") or "")
        if not pixmap.isNull():
            cover.setPixmap(pixmap.scaled(
                72, 100, Qt.AspectRatioMode.KeepAspectRatio,
                Qt.TransformationMode.SmoothTransformation))
        else:
            cover.setText("📖")
        row.addWidget(cover)

        info = QVBoxLayout()
        info.setSpacing(4)
        info.addWidget(self._label(
            book.get("title") or "Sem título",
            "dossierBookTitle"))
        info.addWidget(self._label(
            book.get("author") or "Autor desconhecido",
            "dossierBookAuthor"))
        progress = self._data["progress"]
        if progress and progress.get("total_pages"):
            pct = int(round(progress.get("percentage") or 0))
            info.addWidget(self._label(
                f"📖 Página {progress['current_page']} de "
                f"{progress['total_pages']} ({pct}%)",
                "dossierProgress"))
        info.addStretch()
        row.addLayout(info, stretch=1)
        lay.addLayout(row)

    def _build_synthesis(self, lay: QVBoxLayout):
        lay.addWidget(self._label("🤖 Síntese", _HEADER_STYLE))
        # Cartão padronizado de resposta de IA (B1): estados pensando →
        # concluído/erro, com Parar e Tentar de novo — substitui o label
        # inline que ficava mudo em erro e não oferecia retry.
        self._synthesis_card = AIResponseCard()
        self._synthesis_card.stop_requested.connect(self._on_synthesis_stop)
        self._synthesis_card.retry_requested.connect(self._start_synthesis)
        lay.addWidget(self._synthesis_card)

    def _build_concepts(self, lay: QVBoxLayout):
        lay.addWidget(self._label("💡 Mapa conceitual", _HEADER_STYLE))
        parts = [
            f"{c['display_name']} ({int(c.get('mentions') or 0)})"
            for c in self._data["concepts"]
        ]
        lay.addWidget(self._label("  ·  ".join(parts), _BODY_STYLE))

    @staticmethod
    def _ellipsize(text: str, max_chars: int) -> str:
        text = text or ""
        return text if len(text) <= max_chars else text[:max_chars - 1].rstrip() + "…"

    def _build_related(self, lay: QVBoxLayout):
        related = self._data["related"]
        if not related:
            return
        lay.addWidget(self._label("🔗 Livros relacionados", _HEADER_STYLE))
        for rel in related:
            shared = ", ".join(rel.get("shared") or [])
            # Título e conceitos em DUAS linhas elipsadas: o texto longo numa
            # linha só forçava a largura mínima do botão além do diálogo e
            # criava scroll horizontal (feedback do usuário, 2026-07-06).
            title_line = f"📕 {self._ellipsize(rel['title'], 56)}"
            text = title_line + (
                f"\n      em comum: {self._ellipsize(shared, 60)}" if shared else "")
            btn = QPushButton(text)
            btn.setToolTip(rel["title"] + (f"\nEm comum: {shared}" if shared else ""))
            btn.setMinimumWidth(0)
            btn.setSizePolicy(QSizePolicy.Policy.Ignored, QSizePolicy.Policy.Preferred)
            btn.setCursor(Qt.CursorShape.PointingHandCursor)
            btn.setObjectName("dossierRelatedBtn")
            btn.clicked.connect(
                lambda _c=False, bid=rel["book_id"]: self._open_related(bid))
            lay.addWidget(btn)

    def _build_confidence(self, lay: QVBoxLayout):
        lay.addWidget(self._label("📊 Confiança", _HEADER_STYLE))
        lay.addWidget(self._label(
            format_coverage_label(self._data["coverage"]).capitalize(),
            _BODY_STYLE))

    def _build_annotations(self, lay: QVBoxLayout):
        total = self._data["annotations_total"]
        if total == 0:
            return
        lay.addWidget(self._label(f"📝 Anotações ({total})", _HEADER_STYLE))
        for ann in self._data["annotations_recent"]:
            page = ann.get("page_number")
            prefix = f"p.{page} — " if page else ""
            title = ann.get("title") or ""
            snippet = ann.get("content") or ""
            text = f"{prefix}{title}: {snippet}" if title else f"{prefix}{snippet}"
            lay.addWidget(self._card(text))

    # ── Síntese assíncrona ────────────────────────────────────────────

    def _start_synthesis(self):
        prompt = build_dossier_synthesis_prompt(self._data)
        if not prompt or self._synthesis_card is None:
            return
        if self._worker is not None and self._worker.isRunning():
            return

        graph_store = GraphStore(self._db)
        cached = get_cached_synthesis(self._db, graph_store, self._book_id)
        if cached:
            self._synthesis_card.set_text(cached)
            self._synthesis_card.finish()
            return

        self._synthesis_card.start("Gerando síntese…")
        from src.gui.workers.dossier_synthesis_worker import DossierSynthesisWorker
        self._worker = DossierSynthesisWorker(
            prompt, ollama_url=self._ollama_url, model=self._model, parent=self)
        self._worker.generated.connect(self._on_synthesis_ready)
        self._worker.failed.connect(self._on_synthesis_failed)
        self._worker.start()

    def _on_synthesis_ready(self, text: str):
        if self._synthesis_card is not None:
            self._synthesis_card.set_text(text)
            self._synthesis_card.finish()
        save_synthesis_cache(self._db, GraphStore(self._db), self._book_id, text)

    def _on_synthesis_failed(self, _reason: str):
        if self._synthesis_card is not None:
            self._synthesis_card.fail("Síntese indisponível (IA offline).")

    def _on_synthesis_stop(self):
        if self._worker is not None and self._worker.isRunning():
            self._worker.cancel()
        if self._synthesis_card is not None:
            self._synthesis_card.fail("Síntese cancelada.")

    def _open_related(self, book_id: int):
        self.open_book_requested.emit(book_id)
        self.accept()

    def closeEvent(self, event):
        if self._worker is not None and self._worker.isRunning():
            self._worker.cancel()
        super().closeEvent(event)
