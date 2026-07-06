"""Diálogo do Dossiê do Livro (Fase 4 — roadmap memória/grafo).

Visão rica, por livro, do que o grafo já sabe: mapa conceitual, livros
relacionados, confiança por cobertura, anotações e síntese em texto via LLM.
Só LÊ dados já ingeridos (GraphStore/LibraryDB) — nunca dispara ingestão.
A síntese chega em background; sem Ollama o resto do dossiê segue de pé
(ADR-005).
"""

from PyQt6.QtWidgets import (
    QDialog, QVBoxLayout, QHBoxLayout, QLabel, QPushButton,
    QScrollArea, QWidget, QFrame,
)
from PyQt6.QtCore import Qt, pyqtSignal
from PyQt6.QtGui import QPixmap

from src.core.book_dossier import (
    build_dossier_data,
    build_dossier_synthesis_prompt,
    format_coverage_label,
)
from src.core.graph.graph_store import GraphStore

_HEADER_STYLE = "color: #71717a; font-size: 11px; font-weight: 600;"
_BODY_STYLE = "color: #cbd5e1; font-size: 12px;"


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
        self._synthesis_label: QLabel | None = None

        self.setWindowTitle("📋 Dossiê do Livro")
        self.resize(560, 680)
        self.setStyleSheet("QDialog { background-color: #0f1115; }")

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
        scroll.setStyleSheet("QScrollArea { border: none; background: transparent; }")
        content = QWidget()
        content.setStyleSheet("background: transparent;")
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

    def _label(self, text: str, style: str) -> QLabel:
        lbl = QLabel(text)
        lbl.setWordWrap(True)
        lbl.setStyleSheet(style)
        return lbl

    def _card(self, text: str) -> QFrame:
        frame = QFrame()
        frame.setStyleSheet(
            "QFrame { background-color: #20242d; border: 1px solid #2d333f;"
            " border-radius: 8px; }")
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
        cover.setStyleSheet("background: #18181b; border-radius: 6px; font-size: 28px;")
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
            "color: #e5e7eb; font-size: 16px; font-weight: 700;"))
        info.addWidget(self._label(
            book.get("author") or "Autor desconhecido",
            "color: #818cf8; font-size: 12px;"))
        progress = self._data["progress"]
        if progress and progress.get("total_pages"):
            pct = int(round(progress.get("percentage") or 0))
            info.addWidget(self._label(
                f"📖 Página {progress['current_page']} de "
                f"{progress['total_pages']} ({pct}%)",
                "color: #71717a; font-size: 11px;"))
        info.addStretch()
        row.addLayout(info, stretch=1)
        lay.addLayout(row)

    def _build_synthesis(self, lay: QVBoxLayout):
        lay.addWidget(self._label("🤖 Síntese", _HEADER_STYLE))
        self._synthesis_label = self._label(
            "Gerando síntese…", _BODY_STYLE + " font-style: italic;")
        card = QFrame()
        card.setStyleSheet(
            "QFrame { background-color: #20242d; border: 1px solid #2d333f;"
            " border-radius: 8px; }")
        card_lay = QVBoxLayout(card)
        card_lay.setContentsMargins(12, 10, 12, 10)
        card_lay.addWidget(self._synthesis_label)
        lay.addWidget(card)

    def _build_concepts(self, lay: QVBoxLayout):
        lay.addWidget(self._label("💡 Mapa conceitual", _HEADER_STYLE))
        parts = [
            f"{c['display_name']} ({int(c.get('mentions') or 0)})"
            for c in self._data["concepts"]
        ]
        lay.addWidget(self._label("  ·  ".join(parts), _BODY_STYLE))

    def _build_related(self, lay: QVBoxLayout):
        related = self._data["related"]
        if not related:
            return
        lay.addWidget(self._label("🔗 Livros relacionados", _HEADER_STYLE))
        for rel in related:
            shared = ", ".join(rel.get("shared") or [])
            btn = QPushButton(f"📕 {rel['title']}" + (f"  —  {shared}" if shared else ""))
            btn.setCursor(Qt.CursorShape.PointingHandCursor)
            btn.setStyleSheet(
                "QPushButton { background: transparent; border: 1px solid #3f3f46;"
                " border-radius: 6px; padding: 8px; color: #a5b4fc; font-size: 12px;"
                " text-align: left; }"
                " QPushButton:hover { border-color: #6366f1; }")
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
        if not prompt or self._synthesis_label is None:
            return
        from src.gui.workers.dossier_synthesis_worker import DossierSynthesisWorker
        self._worker = DossierSynthesisWorker(
            prompt, ollama_url=self._ollama_url, model=self._model, parent=self)
        self._worker.generated.connect(self._on_synthesis_ready)
        self._worker.failed.connect(self._on_synthesis_failed)
        self._worker.start()

    def _on_synthesis_ready(self, text: str):
        if self._synthesis_label is not None:
            self._synthesis_label.setStyleSheet(_BODY_STYLE)
            self._synthesis_label.setText(text)

    def _on_synthesis_failed(self, _reason: str):
        if self._synthesis_label is not None:
            self._synthesis_label.setText("Síntese indisponível (IA offline).")

    def _open_related(self, book_id: int):
        self.open_book_requested.emit(book_id)
        self.accept()

    def closeEvent(self, event):
        if self._worker is not None and self._worker.isRunning():
            self._worker.cancel()
        super().closeEvent(event)
