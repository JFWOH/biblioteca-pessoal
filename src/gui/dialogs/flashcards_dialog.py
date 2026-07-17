"""Diálogo de Flashcards: consulta (lista) + modo de estudo com repetição espaçada.

Lê os cards persistidos no app (tabela ``flashcards``) — fonte de verdade
consultável, independente do Anki. O estudo usa o agendamento SM-2 simplificado
de ``src.core.srs``.
"""

from datetime import date

from PyQt6.QtWidgets import (
    QDialog, QVBoxLayout, QHBoxLayout, QLabel, QPushButton, QComboBox,
    QScrollArea, QWidget, QFrame, QStackedWidget, QCheckBox, QLineEdit,
    QDialogButtonBox, QMessageBox,
)
from PyQt6.QtCore import Qt, pyqtSignal

from src.core import srs
from src.gui.styles import emoji_icon


class _FlashcardCard(QFrame):
    """Item de flashcard na lista (frente/verso + origem + excluir)."""

    delete_requested = pyqtSignal(int)

    def __init__(self, fc: dict, book_title: str, parent=None):
        super().__init__(parent)
        self._fc = fc
        self.setObjectName("flashcardItem")
        layout = QVBoxLayout(self)
        layout.setContentsMargins(12, 10, 12, 10)
        layout.setSpacing(6)

        header = QHBoxLayout()
        is_new = not (fc.get("due_date") or "")
        badge = QLabel("novo" if is_new else f"revisar {fc.get('due_date', '')}")
        badge.setObjectName("flashcardBadgeNew" if is_new else "flashcardBadgeDue")
        header.addWidget(badge)
        header.addStretch()
        if book_title:
            origin = QLabel(f"📖 {book_title}")
            origin.setObjectName("flashcardOrigin")
            header.addWidget(origin)
        del_btn = QPushButton("✕")
        del_btn.setFixedSize(20, 20)
        del_btn.setObjectName("flashcardDeleteBtn")
        del_btn.clicked.connect(lambda: self.delete_requested.emit(fc.get("id", 0)))
        header.addWidget(del_btn)
        layout.addLayout(header)

        front = QLabel(fc.get("front", ""))
        front.setWordWrap(True)
        front.setObjectName("flashcardFront")
        layout.addWidget(front)

        back = QLabel(fc.get("back", ""))
        back.setWordWrap(True)
        back.setObjectName("flashcardBack")
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
        self.setObjectName("flashcardsDialog")
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
        title.setObjectName("flashcardsTitle")
        top.addWidget(title)
        top.addStretch()

        self._book_filter = QComboBox()
        self._book_filter.setMinimumWidth(180)
        self._book_filter.setObjectName("flashcardsBookFilter")
        self._book_filter.currentIndexChanged.connect(self._on_filter_changed)
        top.addWidget(self._book_filter)

        # Ação em lote: gera cards a partir dos DESTAQUES do livro selecionado
        # (tarefa 3.3). Só habilita quando há um livro específico no filtro.
        self._highlights_btn = QPushButton(" Dos destaques")
        self._highlights_btn.setIcon(emoji_icon("🃏"))
        self._highlights_btn.setObjectName("flashcardsHighlightBtn")
        self._highlights_btn.setToolTip(
            "Gerar flashcards (pergunta/resposta) a partir dos destaques deste livro")
        self._highlights_btn.clicked.connect(self._generate_from_highlights)
        top.addWidget(self._highlights_btn)

        self._study_btn = QPushButton("Estudar")
        self._study_btn.setObjectName("flashcardsStudyBtn")
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
        self._empty_lbl.setObjectName("flashcardsEmptyLabel")
        self._empty_lbl.setVisible(False)
        lay.addWidget(self._empty_lbl)

        self._count_lbl = QLabel("")
        self._count_lbl.setObjectName("flashcardsCountLabel")
        lay.addWidget(self._count_lbl)
        return page

    def _build_study_page(self) -> QWidget:
        page = QWidget()
        lay = QVBoxLayout(page)
        lay.setContentsMargins(0, 0, 0, 0)
        lay.setSpacing(12)

        self._progress_lbl = QLabel("")
        self._progress_lbl.setObjectName("flashcardsProgressLabel")
        lay.addWidget(self._progress_lbl)

        card = QFrame()
        card.setObjectName("flashcardsStudyCard")
        card_lay = QVBoxLayout(card)
        card_lay.setContentsMargins(18, 18, 18, 18)
        card_lay.setSpacing(12)

        self._front_lbl = QLabel("")
        self._front_lbl.setWordWrap(True)
        self._front_lbl.setObjectName("flashcardsStudyFront")
        card_lay.addWidget(self._front_lbl)

        self._sep = QFrame()
        self._sep.setFixedHeight(1)
        self._sep.setObjectName("flashcardsStudySep")
        self._sep.setVisible(False)
        card_lay.addWidget(self._sep)

        self._back_lbl = QLabel("")
        self._back_lbl.setWordWrap(True)
        self._back_lbl.setObjectName("flashcardsStudyBack")
        self._back_lbl.setVisible(False)
        card_lay.addWidget(self._back_lbl)
        card_lay.addStretch()
        lay.addWidget(card, 1)

        self._reveal_btn = QPushButton("Mostrar resposta")
        self._reveal_btn.setObjectName("flashcardsRevealBtn")
        self._reveal_btn.clicked.connect(self._reveal_answer)
        lay.addWidget(self._reveal_btn)

        # Botões de nota (escondidos até revelar)
        self._grade_row = QHBoxLayout()
        self._grade_row.setSpacing(6)
        self._grade_buttons = {}
        # Cores fixas por nota (enum de 4 valores conhecidos em tempo de
        # escrita — não é dado de runtime) — cada uma vira um objectName
        # dedicado (#flashcardsGrade<Nota>) com regras nos 3 temas.
        grade_object_names = {
            "again": "flashcardsGradeAgain",
            "hard": "flashcardsGradeHard",
            "good": "flashcardsGradeGood",
            "easy": "flashcardsGradeEasy",
        }
        for g in srs.GRADES:
            btn = QPushButton(srs.GRADE_LABELS[g])
            btn.setObjectName(grade_object_names[g])
            btn.clicked.connect(lambda _checked=False, gr=g: self._grade(gr))
            self._grade_buttons[g] = btn
            self._grade_row.addWidget(btn)
        self._grade_widget = QWidget()
        self._grade_widget.setLayout(self._grade_row)
        self._grade_widget.setVisible(False)
        lay.addWidget(self._grade_widget)

        back_btn = QPushButton("← Voltar à lista")
        back_btn.setObjectName("flashcardsBackBtn")
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

        # "Dos destaques" só faz sentido com um livro específico selecionado.
        worker = getattr(self, "_highlights_worker", None)
        generating = worker is not None and worker.isRunning()
        self._highlights_btn.setEnabled(book_id is not None and not generating)

    def _on_delete(self, fc_id: int):
        self._db.delete_flashcard(fc_id)
        self._reload_books_filter()
        self._refresh_list()

    # ── Cards a partir dos destaques (tarefa 3.3) ─────────────────────

    def _ollama_url(self) -> str:
        parent = self.parent()
        config = getattr(parent, "_config", None) if parent is not None else None
        if config is not None:
            try:
                return config.get("rag.ollama_url", "http://localhost:11434")
            except Exception:
                pass
        return "http://localhost:11434"

    def _generate_from_highlights(self):
        """Gera, em lote, um card por destaque do livro selecionado."""
        book_id = self._selected_book_id()
        if book_id is None:
            QMessageBox.information(
                self, "Flashcards dos destaques",
                "Selecione um livro específico no filtro para gerar cards dos "
                "destaques dele.")
            return
        try:
            highlights = self._db.get_annotations(book_id, "highlight")
        except Exception:
            highlights = []
        texts = [(h.get("content") or "").strip() for h in highlights]
        texts = [t for t in texts if t]
        if not texts:
            QMessageBox.information(
                self, "Flashcards dos destaques",
                "Este livro ainda não tem destaques com texto para virar "
                "flashcards.")
            return

        from src.gui.workers.flashcard_qa_worker import HighlightCardsWorker
        self._highlights_btn.setEnabled(False)
        self._highlights_btn.setText(f" Gerando… (0/{len(texts)})")
        self._highlights_worker = HighlightCardsWorker(
            texts, ollama_url=self._ollama_url(), parent=self)
        self._highlights_worker.progress.connect(self._on_highlights_progress)
        self._highlights_worker.cards_ready.connect(
            lambda cards, bid=book_id: self._on_highlights_ready(cards, bid))
        self._highlights_worker.failed.connect(self._on_highlights_failed)
        self._highlights_worker.start()

    def _on_highlights_progress(self, done: int, total: int):
        self._highlights_btn.setText(f" Gerando… ({done}/{total})")

    def _on_highlights_ready(self, cards: list, book_id):
        self._reset_highlights_btn()
        if not cards:
            QMessageBox.information(
                self, "Flashcards dos destaques",
                "Nenhum card foi gerado a partir dos destaques.")
            return
        preview = _HighlightCardsPreview(cards, parent=self)
        if preview.exec() == QDialog.DialogCode.Accepted:
            selected = preview.selected_cards()
            saved = 0
            for c in selected:
                try:
                    self._db.add_flashcard(
                        front=c["front"], back=c["back"], book_id=book_id)
                    saved += 1
                except Exception:
                    pass
            self._reload_books_filter()
            self._refresh_list()
            if saved:
                QMessageBox.information(
                    self, "Flashcards dos destaques",
                    f"{saved} flashcard(s) salvo(s).")

    def _on_highlights_failed(self, reason: str):
        self._reset_highlights_btn()
        QMessageBox.warning(
            self, "Flashcards dos destaques",
            f"Não foi possível gerar os cards agora:\n{reason}")

    def _reset_highlights_btn(self):
        self._highlights_btn.setText(" Dos destaques")
        self._highlights_btn.setEnabled(self._selected_book_id() is not None)

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


class _HighlightCardsPreview(QDialog):
    """Preview editável/selecionável dos cards propostos dos destaques (3.3).

    Cada linha: [x] Incluir · frente (pergunta) · verso (resposta). Salva só os
    marcados COM frente e verso preenchidos — o usuário revisa e corrige os
    fallbacks (pergunta em branco) antes de gravar.
    """

    def __init__(self, cards: list, parent=None):
        super().__init__(parent)
        self.setWindowTitle("🃏 Cards propostos dos destaques")
        # Reaproveita o tema já estilizado do diálogo de flashcards (3 temas).
        self.setObjectName("flashcardsDialog")
        self.resize(620, 560)
        self._rows: list = []
        self._setup_ui(cards)

    def _setup_ui(self, cards: list):
        root = QVBoxLayout(self)
        root.setContentsMargins(16, 16, 16, 16)
        root.setSpacing(10)

        title = QLabel("Revise, edite e escolha os cards a salvar")
        title.setObjectName("flashcardsTitle")
        root.addWidget(title)

        scroll = QScrollArea()
        scroll.setWidgetResizable(True)
        scroll.setFrameShape(QScrollArea.Shape.NoFrame)
        container = QWidget()
        col = QVBoxLayout(container)
        col.setContentsMargins(0, 0, 0, 0)
        col.setSpacing(8)
        col.setAlignment(Qt.AlignmentFlag.AlignTop)

        for card in cards:
            front = (card.get("front") or "").strip()
            back = (card.get("back") or "").strip()

            row = QFrame()
            row.setObjectName("flashcardItem")
            rlay = QVBoxLayout(row)
            rlay.setContentsMargins(10, 8, 10, 8)
            rlay.setSpacing(4)

            check = QCheckBox("Incluir")
            check.setChecked(bool(front and back))
            rlay.addWidget(check)

            front_edit = QLineEdit(front)
            front_edit.setPlaceholderText("Pergunta (frente)")
            rlay.addWidget(front_edit)

            back_edit = QLineEdit(back)
            back_edit.setPlaceholderText("Resposta (verso)")
            rlay.addWidget(back_edit)

            self._rows.append((check, front_edit, back_edit))
            col.addWidget(row)

        scroll.setWidget(container)
        root.addWidget(scroll, 1)

        buttons = QDialogButtonBox(
            QDialogButtonBox.StandardButton.Save
            | QDialogButtonBox.StandardButton.Cancel)
        buttons.button(QDialogButtonBox.StandardButton.Save).setText(
            "Salvar selecionados")
        buttons.accepted.connect(self.accept)
        buttons.rejected.connect(self.reject)
        root.addWidget(buttons)

    def selected_cards(self) -> list:
        out = []
        for check, front_edit, back_edit in self._rows:
            if not check.isChecked():
                continue
            front = front_edit.text().strip()
            back = back_edit.text().strip()
            if front and back:
                out.append({"front": front, "back": back})
        return out
