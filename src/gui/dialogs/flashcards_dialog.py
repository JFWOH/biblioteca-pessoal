"""Diálogo de Flashcards: consulta (lista) + modo de estudo com repetição espaçada.

Lê os cards persistidos no app (tabela ``flashcards``) — fonte de verdade
consultável, independente do Anki. O estudo usa o agendamento SM-2 simplificado
de ``src.core.srs``.
"""

from datetime import date

from PyQt6.QtWidgets import (
    QDialog, QVBoxLayout, QHBoxLayout, QLabel, QPushButton, QComboBox,
    QScrollArea, QWidget, QFrame, QStackedWidget,
)
from PyQt6.QtCore import Qt, pyqtSignal

from src.core import srs


class _FlashcardCard(QFrame):
    """Item de flashcard na lista (frente/verso + origem + excluir)."""

    delete_requested = pyqtSignal(int)

    def __init__(self, fc: dict, book_title: str, parent=None):
        super().__init__(parent)
        self._fc = fc
        self.setStyleSheet(
            "QFrame { background-color: #20242d; border: 1px solid #2d333f;"
            " border-radius: 8px; }"
        )
        layout = QVBoxLayout(self)
        layout.setContentsMargins(12, 10, 12, 10)
        layout.setSpacing(6)

        header = QHBoxLayout()
        is_new = not (fc.get("due_date") or "")
        badge = QLabel("novo" if is_new else f"revisar {fc.get('due_date', '')}")
        badge.setStyleSheet(
            "color: #10b981; font-size: 10px; font-weight: 600;"
            if is_new else "color: #94a3b8; font-size: 10px;"
        )
        header.addWidget(badge)
        header.addStretch()
        if book_title:
            origin = QLabel(f"📖 {book_title}")
            origin.setStyleSheet("color: #818cf8; font-size: 10px;")
            header.addWidget(origin)
        del_btn = QPushButton("✕")
        del_btn.setFixedSize(20, 20)
        del_btn.setStyleSheet(
            "QPushButton { background: transparent; border: none; color: #52525b; font-size: 12px; }"
            " QPushButton:hover { color: #ef4444; }"
        )
        del_btn.clicked.connect(lambda: self.delete_requested.emit(fc.get("id", 0)))
        header.addWidget(del_btn)
        layout.addLayout(header)

        front = QLabel(fc.get("front", ""))
        front.setWordWrap(True)
        front.setStyleSheet("color: #e5e7eb; font-size: 13px; font-weight: 600;")
        layout.addWidget(front)

        back = QLabel(fc.get("back", ""))
        back.setWordWrap(True)
        back.setStyleSheet("color: #cbd5e1; font-size: 12px;")
        layout.addWidget(back)


class FlashcardsDialog(QDialog):
    def __init__(self, db, current_book_id=None, parent=None):
        super().__init__(parent)
        self._db = db
        self._current_book_id = current_book_id
        self._book_titles = {b["id"]: b.get("title", "") for b in db.get_all_books()}

        # Estado do estudo
        self._queue: list[dict] = []
        self._index = 0
        self._answer_shown = False

        self.setWindowTitle("🃏 Flashcards")
        self.resize(560, 640)
        self.setStyleSheet("QDialog { background-color: #0f1115; }")
        self._setup_ui()
        self._reload_books_filter()
        self._refresh_list()

    # ── UI ────────────────────────────────────────────────────────────

    def _setup_ui(self):
        root = QVBoxLayout(self)
        root.setContentsMargins(16, 16, 16, 16)
        root.setSpacing(12)

        # Cabeçalho: filtro por livro + botão estudar
        top = QHBoxLayout()
        title = QLabel("🃏 Flashcards")
        title.setStyleSheet("color: #e5e7eb; font-size: 16px; font-weight: 700;")
        top.addWidget(title)
        top.addStretch()

        self._book_filter = QComboBox()
        self._book_filter.setMinimumWidth(180)
        self._book_filter.setStyleSheet(
            "QComboBox { background: #161920; border: 1px solid #2d333f; border-radius: 6px;"
            " padding: 5px 8px; color: #e4e4e7; font-size: 12px; }"
            " QComboBox QAbstractItemView { background: #161920; color: #e4e4e7;"
            " selection-background-color: #2d333f; }"
        )
        self._book_filter.currentIndexChanged.connect(self._on_filter_changed)
        top.addWidget(self._book_filter)

        self._study_btn = QPushButton("Estudar")
        self._study_btn.setStyleSheet(
            "QPushButton { background: #10b981; color: #06281e; border: none; border-radius: 6px;"
            " padding: 6px 14px; font-size: 12px; font-weight: 600; }"
            " QPushButton:hover { background: #34d399; }"
            " QPushButton:disabled { background: #1f2937; color: #4b5563; }"
        )
        self._study_btn.clicked.connect(self._start_study)
        top.addWidget(self._study_btn)
        root.addLayout(top)

        self._stack = QStackedWidget()
        root.addWidget(self._stack, 1)

        # Página 0: lista
        self._stack.addWidget(self._build_list_page())
        # Página 1: estudo
        self._stack.addWidget(self._build_study_page())

    def _build_list_page(self) -> QWidget:
        page = QWidget()
        lay = QVBoxLayout(page)
        lay.setContentsMargins(0, 0, 0, 0)
        lay.setSpacing(8)

        self._scroll = QScrollArea()
        self._scroll.setWidgetResizable(True)
        self._scroll.setFrameShape(QScrollArea.Shape.NoFrame)
        self._list_container = QWidget()
        self._list_layout = QVBoxLayout(self._list_container)
        self._list_layout.setContentsMargins(0, 0, 0, 0)
        self._list_layout.setSpacing(8)
        self._list_layout.setAlignment(Qt.AlignmentFlag.AlignTop)
        self._scroll.setWidget(self._list_container)
        lay.addWidget(self._scroll, 1)

        self._empty_lbl = QLabel(
            "Nenhum flashcard ainda.\n\nCrie cards pela seleção no leitor (🃏 Flashcard)\n"
            "ou pelo Assistente, e eles aparecem aqui para consulta e estudo."
        )
        self._empty_lbl.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self._empty_lbl.setStyleSheet("color: #6b7280; font-size: 13px;")
        self._empty_lbl.setVisible(False)
        lay.addWidget(self._empty_lbl)

        self._count_lbl = QLabel("")
        self._count_lbl.setStyleSheet("color: #52525b; font-size: 11px;")
        lay.addWidget(self._count_lbl)
        return page

    def _build_study_page(self) -> QWidget:
        page = QWidget()
        lay = QVBoxLayout(page)
        lay.setContentsMargins(0, 0, 0, 0)
        lay.setSpacing(12)

        self._progress_lbl = QLabel("")
        self._progress_lbl.setStyleSheet("color: #94a3b8; font-size: 12px;")
        lay.addWidget(self._progress_lbl)

        card = QFrame()
        card.setStyleSheet("QFrame { background: #161920; border: 1px solid #2d333f; border-radius: 10px; }")
        card_lay = QVBoxLayout(card)
        card_lay.setContentsMargins(18, 18, 18, 18)
        card_lay.setSpacing(12)

        self._front_lbl = QLabel("")
        self._front_lbl.setWordWrap(True)
        self._front_lbl.setStyleSheet("color: #e5e7eb; font-size: 15px; font-weight: 600;")
        card_lay.addWidget(self._front_lbl)

        self._sep = QFrame()
        self._sep.setFixedHeight(1)
        self._sep.setStyleSheet("background: #2d333f;")
        self._sep.setVisible(False)
        card_lay.addWidget(self._sep)

        self._back_lbl = QLabel("")
        self._back_lbl.setWordWrap(True)
        self._back_lbl.setStyleSheet("color: #cbd5e1; font-size: 14px;")
        self._back_lbl.setVisible(False)
        card_lay.addWidget(self._back_lbl)
        card_lay.addStretch()
        lay.addWidget(card, 1)

        self._reveal_btn = QPushButton("Mostrar resposta")
        self._reveal_btn.setStyleSheet(
            "QPushButton { background: #2563eb; color: white; border: none; border-radius: 8px;"
            " padding: 10px; font-size: 13px; font-weight: 600; }"
            " QPushButton:hover { background: #1d4ed8; }"
        )
        self._reveal_btn.clicked.connect(self._reveal_answer)
        lay.addWidget(self._reveal_btn)

        # Botões de nota (escondidos até revelar)
        self._grade_row = QHBoxLayout()
        self._grade_row.setSpacing(6)
        self._grade_buttons = {}
        grade_colors = {
            "again": "#ef4444", "hard": "#f59e0b", "good": "#10b981", "easy": "#3b82f6",
        }
        for g in srs.GRADES:
            btn = QPushButton(srs.GRADE_LABELS[g])
            color = grade_colors[g]
            btn.setStyleSheet(
                f"QPushButton {{ background: transparent; color: {color}; border: 1px solid {color};"
                f" border-radius: 8px; padding: 8px 6px; font-size: 12px; font-weight: 600; }}"
                f" QPushButton:hover {{ background: {color}; color: #0f1115; }}"
            )
            btn.clicked.connect(lambda _checked=False, gr=g: self._grade(gr))
            self._grade_buttons[g] = btn
            self._grade_row.addWidget(btn)
        self._grade_widget = QWidget()
        self._grade_widget.setLayout(self._grade_row)
        self._grade_widget.setVisible(False)
        lay.addWidget(self._grade_widget)

        back_btn = QPushButton("← Voltar à lista")
        back_btn.setStyleSheet(
            "QPushButton { background: transparent; color: #94a3b8; border: none; font-size: 12px; }"
            " QPushButton:hover { color: #e5e7eb; }"
        )
        back_btn.clicked.connect(self._back_to_list)
        lay.addWidget(back_btn)
        return page

    # ── Filtro / lista ────────────────────────────────────────────────

    def _reload_books_filter(self):
        self._book_filter.blockSignals(True)
        self._book_filter.clear()
        self._book_filter.addItem("Todos os livros", None)
        # apenas livros que têm cards
        book_ids = {fc.get("book_id") for fc in self._db.get_flashcards()}
        for bid in sorted(b for b in book_ids if b is not None):
            self._book_filter.addItem(self._book_titles.get(bid, f"Livro {bid}"), bid)
        if None in book_ids:
            self._book_filter.addItem("Sem livro associado", -1)
        # seleciona o livro atual, se houver cards dele
        if self._current_book_id is not None:
            idx = self._book_filter.findData(self._current_book_id)
            if idx >= 0:
                self._book_filter.setCurrentIndex(idx)
        self._book_filter.blockSignals(False)

    def _selected_book_id(self):
        data = self._book_filter.currentData()
        if data == -1:
            return None  # "Sem livro" — tratado como book_id NULL na consulta
        return data

    def _on_filter_changed(self):
        self._refresh_list()

    def _refresh_list(self):
        # limpa
        while self._list_layout.count():
            item = self._list_layout.takeAt(0)
            if item.widget():
                item.widget().deleteLater()

        book_id = self._selected_book_id()
        cards = self._db.get_flashcards(book_id)
        for fc in cards:
            widget = _FlashcardCard(fc, self._book_titles.get(fc.get("book_id")) or "")
            widget.delete_requested.connect(self._on_delete)
            self._list_layout.addWidget(widget)

        self._empty_lbl.setVisible(len(cards) == 0)
        self._scroll.setVisible(len(cards) > 0)
        self._count_lbl.setText(f"{len(cards)} flashcard(s)")

        due = self._db.get_due_flashcards(date.today().isoformat(), book_id)
        n = len(due)
        self._study_btn.setText(f"Estudar ({n})" if n else "Estudar")
        self._study_btn.setEnabled(n > 0)

    def _on_delete(self, fc_id: int):
        self._db.delete_flashcard(fc_id)
        self._reload_books_filter()
        self._refresh_list()

    # ── Estudo ────────────────────────────────────────────────────────

    def _start_study(self):
        self._queue = self._db.get_due_flashcards(date.today().isoformat(), self._selected_book_id())
        if not self._queue:
            return
        self._index = 0
        self._stack.setCurrentIndex(1)
        self._show_current()

    def _show_current(self):
        self._answer_shown = False
        fc = self._queue[self._index]
        self._front_lbl.setText(fc.get("front", ""))
        self._back_lbl.setText(fc.get("back", ""))
        self._back_lbl.setVisible(False)
        self._sep.setVisible(False)
        self._grade_widget.setVisible(False)
        self._reveal_btn.setVisible(True)
        self._progress_lbl.setText(f"Card {self._index + 1} de {len(self._queue)}")

        # hints de intervalo nos botões de nota
        state = self._state_of(fc)
        previews = srs.preview_intervals(state)
        for g, btn in self._grade_buttons.items():
            btn.setText(f"{srs.GRADE_LABELS[g]} · {previews[g]}")

    def _reveal_answer(self):
        self._answer_shown = True
        self._back_lbl.setVisible(True)
        self._sep.setVisible(True)
        self._reveal_btn.setVisible(False)
        self._grade_widget.setVisible(True)

    def _grade(self, grade: str):
        fc = self._queue[self._index]
        state = self._state_of(fc)
        new_state, due = srs.review(state, grade)
        self._db.update_flashcard_review(
            fc.get("id"), due.isoformat(), new_state.interval_days,
            new_state.ease, new_state.reps, new_state.lapses,
        )
        self._index += 1
        if self._index >= len(self._queue):
            self._back_to_list()
        else:
            self._show_current()

    @staticmethod
    def _state_of(fc: dict) -> srs.CardState:
        return srs.CardState(
            interval_days=int(fc.get("interval_days", 0) or 0),
            ease=float(fc.get("ease", srs.DEFAULT_EASE) or srs.DEFAULT_EASE),
            reps=int(fc.get("reps", 0) or 0),
            lapses=int(fc.get("lapses", 0) or 0),
        )

    def _back_to_list(self):
        self._stack.setCurrentIndex(0)
        self._reload_books_filter()
        self._refresh_list()
