"""Painel de chat RAG integrado ao MainWindow.

Widget premium com chat de IA local, streaming de respostas, exibição de
fontes bibliográficas e controle de indexação — tudo rodando localmente.
"""

from __future__ import annotations

import uuid

from PyQt6.QtCore import Qt, QEvent, pyqtSignal
from PyQt6.QtGui import QFont, QTextCursor
from PyQt6.QtWidgets import (
    QWidget, QVBoxLayout, QHBoxLayout, QLabel, QLineEdit,
    QPushButton, QTextEdit, QListWidget, QListWidgetItem,
    QProgressBar, QFrame, QSplitter, QComboBox,
)


class RAGPanel(QWidget):
    """Painel de Assistente de IA local baseado em RAG.

    Exibe uma interface de chat onde o usuário pode fazer perguntas sobre
    seus livros. As respostas são geradas por um LLM local (via Ollama)
    usando os livros e anotações como contexto (RAG).

    Signals:
        index_requested: Emitido quando o usuário clica em 'Reindexar'.
        index_book_requested(int): Emitido para indexar um livro específico.
        query_requested(str): Emitido com a pergunta do usuário.
        stop_requested: Emitido quando o usuário cancela a geração.
    """

    index_requested = pyqtSignal()
    index_book_requested = pyqtSignal(int)
    query_requested = pyqtSignal(str)
    stop_requested = pyqtSignal()
    model_changed = pyqtSignal(str)    # model_id — usuário trocou o modelo
    close_requested = pyqtSignal()     # Emitido para ocultar o painel no modo side-by-side
    back_requested = pyqtSignal()      # Emitido para voltar à biblioteca no modo tela cheia
    save_annotation_requested = pyqtSignal(int, int, str) # book_id, page, content
    clear_chat_requested = pyqtSignal()  # limpar a memória conversacional do contexto atual
    feedback_submitted = pyqtSignal(int, dict)  # rating (+1/-1), context dict
    feedback_reason_submitted = pyqtSignal(int, str)  # feedback_id, reason (motivo do 👎)
    source_clicked = pyqtSignal(int, int)  # book_id, page (0-based do leitor) — Tarefa 3.1
    retry_with_reason_requested = pyqtSignal(str, str)  # query, reason — Tarefa 3.8

    # Chips de motivo do 👎: rótulo exibido → chave canônica gravada em reason.
    _REASON_CHIPS = (
        ("Errada", "resposta_errada"),
        ("Incompleta", "incompleta"),
        ("Fora do contexto", "fora_contexto"),
        ("Genérica", "generica"),
    )

    def __init__(self, parent=None) -> None:
        super().__init__(parent)
        self._is_generating = False
        self._full_answer = ""
        self._reading_context = None
        self._is_standalone = False
        # Config (injetada pelo MainWindow via set_config): persiste a
        # preferência de colapso da sidebar (fontes/modelo/indexação) entre
        # sessões. Sem config, o padrão embutido (recolhida) ainda vale — só
        # não persiste (ADR-005, degradação graciosa).
        self._config = None
        # Feedback (Fase 1b): id de sessão por pergunta + última query, para
        # gravar 👍/👎 em agent_feedback; 1 voto por resposta.
        self._current_session_id = ""
        self._last_query = ""
        self._feedback_given = False
        # Motivo do 👎: id da linha persistida (chega via on_feedback_persisted)
        # e motivo escolhido antes do id (defensivo — ADR-005, nunca quebra a UI).
        self._last_feedback_id: int | None = None
        self._pending_reason: str | None = None
        # 3.8: motivo do último 👎 (habilita o botão "Responder de novo").
        self._last_reason_for_retry: str | None = None
        # Fontes clicáveis (Tarefa 3.1): provedor da lista de livros do banco,
        # usado para resolver citações [Título, p. X] → book_id (fuzzy match).
        self._books_provider = None
        self._setup_ui()

    # ── Construção da UI ───────────────────────────────────────────────────────

    def _setup_ui(self) -> None:
        root = QVBoxLayout(self)
        root.setContentsMargins(0, 0, 0, 0)
        root.setSpacing(0)

        # ── Header ─────────────────────────────────────────────────────────────
        self._header = QWidget()
        self._header.setObjectName("ragHeader")
        self._header.setFixedHeight(64)
        h_layout = QHBoxLayout(self._header)
        h_layout.setContentsMargins(24, 0, 24, 0)

        # Botão voltar (para modo tela cheia)
        self._back_btn = QPushButton("← Biblioteca")
        self._back_btn.setStyleSheet("""
            QPushButton {
                background: transparent;
                color: #10b981;
                border: none;
                font-weight: 500;
                font-size: 13px;
                padding-right: 12px;
            }
            QPushButton:hover { color: #34d399; }
        """)
        self._back_btn.setVisible(False)
        self._back_btn.clicked.connect(self.back_requested.emit)
        h_layout.addWidget(self._back_btn)

        icon_lbl = QLabel("🧠")
        icon_lbl.setFont(QFont("Segoe UI Emoji", 22))
        h_layout.addWidget(icon_lbl)

        title_col = QVBoxLayout()
        title_col.setSpacing(0)
        self._title_lbl = QLabel("Assistente de Biblioteca")
        self._sub_lbl = QLabel("Pergunte sobre seus livros e anotações · 100% local")
        title_col.addWidget(self._title_lbl)
        title_col.addWidget(self._sub_lbl)
        h_layout.addLayout(title_col, stretch=1)

        # Status badge do Ollama
        self._status_badge = QLabel("⚫ Verificando…")
        self._status_badge.setObjectName("badge")
        self._status_badge.setStyleSheet("""
            background: #27272a; color: #a1a1aa; border-radius: 10px;
            padding: 4px 12px; font-size: 11px; font-weight: 600;
        """)
        h_layout.addWidget(self._status_badge)

        # Botão recolher/expandir a barra lateral (fontes, modelo, indexação) —
        # recolhido, a resposta do assistente ocupa toda a largura do painel.
        self._sidebar_toggle_btn = QPushButton("⟩")
        self._sidebar_toggle_btn.setFixedSize(28, 28)
        self._sidebar_toggle_btn.setCheckable(True)
        self._sidebar_toggle_btn.setCursor(Qt.CursorShape.PointingHandCursor)
        self._sidebar_toggle_btn.setToolTip("Recolher/expandir o painel lateral (fontes, modelo)")
        self._sidebar_toggle_btn.setStyleSheet("""
            QPushButton { background: transparent; color: #a1a1aa; border: none;
                          border-radius: 4px; font-size: 15px; font-weight: bold; }
            QPushButton:hover { background: #3f3f46; color: white; }
            QPushButton:checked { color: #10b981; }
        """)
        self._sidebar_toggle_btn.clicked.connect(self._toggle_sidebar)
        h_layout.addWidget(self._sidebar_toggle_btn)

        # Botão Fechar (Escape Hatch)
        self._close_btn = QPushButton("✕")
        self._close_btn.setFixedSize(28, 28)
        self._close_btn.setCursor(Qt.CursorShape.PointingHandCursor)
        self._close_btn.setStyleSheet("""
            QPushButton {
                background: transparent;
                color: #a1a1aa;
                border: none;
                border-radius: 4px;
                font-size: 16px;
                font-weight: bold;
            }
            QPushButton:hover {
                background: #ef4444;
                color: white;
            }
        """)
        self._close_btn.clicked.connect(self.close_requested.emit)
        h_layout.addWidget(self._close_btn)

        root.addWidget(self._header)

        # ── Corpo central: splitter (chat | fontes) ────────────────────────────
        splitter = QSplitter(Qt.Orientation.Horizontal)
        splitter.setHandleWidth(1)
        splitter.setStyleSheet("QSplitter::handle { background: #27272a; }")

        # ── Painel esquerdo: chat ──────────────────────────────────────────────
        self._chat_widget = QWidget()
        chat_layout = QVBoxLayout(self._chat_widget)
        chat_layout.setContentsMargins(24, 16, 16, 0)
        chat_layout.setSpacing(12)

        # Área de resposta
        self._response_label = QLabel("💬 Resposta")
        chat_layout.addWidget(self._response_label)

        # Indicador PROEMINENTE de raciocínio/preparo do modelo. Fica acima da
        # resposta e só aparece enquanto o modelo "pensa" (status "💭") ou o
        # modelo está sendo carregado/trocado (status "🧠") — o período em que
        # a UI parecia travada ("sem resposta"). Some assim que o 1º token de
        # conteúdo chega. Estilizado por objectName nos 3 temas (styles.py).
        self._thinking_indicator = QLabel("")
        self._thinking_indicator.setObjectName("ragThinkingIndicator")
        self._thinking_indicator.setWordWrap(True)
        self._thinking_indicator.setVisible(False)
        chat_layout.addWidget(self._thinking_indicator)

        self._response_area = QTextEdit()
        self._response_area.setReadOnly(True)
        self._response_area.setObjectName("responseArea")
        self._response_area.setPlaceholderText(
            "Faça uma pergunta sobre seus livros…\n\n"
            "Exemplos:\n"
            "  • Quais livros abordam o tema de distopia?\n"
            "  • Resuma as minhas anotações sobre Dom Casmurro\n"
            "  • Quais são os conceitos principais de Python Fluente?"
        )
        self._response_area.setMinimumHeight(200)
        chat_layout.addWidget(self._response_area, stretch=1)

        # Container para botões de ação na resposta
        action_btns_layout = QHBoxLayout()
        action_btns_layout.addStretch()

        # Botão de Flashcard
        self._flashcard_btn = QPushButton("🃏 Criar Flashcard")
        self._flashcard_btn.setVisible(False)
        self._flashcard_btn.setStyleSheet("""
            QPushButton {
                background-color: rgba(37, 99, 235, 0.15);
                color: #3b82f6;
                border: 1px solid #2563eb;
                border-radius: 8px;
                padding: 8px 16px;
                font-weight: bold;
                font-size: 12px;
            }
            QPushButton:hover {
                background-color: rgba(37, 99, 235, 0.25);
            }
        """)
        self._flashcard_btn.clicked.connect(self._on_flashcard_clicked)
        action_btns_layout.addWidget(self._flashcard_btn)

        # Botão de Salvar Anotação Manual (Human-in-the-Loop)
        self._save_note_btn = QPushButton("💾 Salvar como Anotação")
        self._save_note_btn.setVisible(False)
        self._save_note_btn.setStyleSheet("""
            QPushButton {
                background-color: rgba(16, 185, 129, 0.15);
                color: #10b981;
                border: 1px solid #059669;
                border-radius: 8px;
                padding: 8px 16px;
                font-weight: bold;
                font-size: 12px;
            }
            QPushButton:hover {
                background-color: rgba(16, 185, 129, 0.25);
            }
            QPushButton:disabled {
                background-color: rgba(39, 39, 42, 0.5);
                color: #52525b;
                border: 1px solid #3f3f46;
            }
        """)
        self._save_note_btn.clicked.connect(self._on_save_note_clicked)
        action_btns_layout.addWidget(self._save_note_btn)

        # Feedback 👍/👎 (Fase 1b): avalia a resposta → agent_feedback.
        # Estilo "ghost" discreto, espelhando selection_popover.
        _fb_style = """
            QPushButton {
                background: transparent;
                border: 1px solid #3f3f46;
                border-radius: 8px;
                color: #9ca3af;
                padding: 8px 12px;
                font-size: 12px;
            }
            QPushButton:hover { background: rgba(16, 185, 129, 0.12); color: #10b981; }
            QPushButton:disabled { color: #52525b; border-color: #2a2a2e; }
        """
        self._thumbs_up_btn = QPushButton("👍 Útil")
        self._thumbs_up_btn.setVisible(False)
        self._thumbs_up_btn.setStyleSheet(_fb_style)
        self._thumbs_up_btn.clicked.connect(lambda: self._on_feedback_clicked(1))
        action_btns_layout.addWidget(self._thumbs_up_btn)

        self._thumbs_down_btn = QPushButton("👎 Não ajudou")
        self._thumbs_down_btn.setVisible(False)
        self._thumbs_down_btn.setStyleSheet(_fb_style)
        self._thumbs_down_btn.clicked.connect(lambda: self._on_feedback_clicked(-1))
        action_btns_layout.addWidget(self._thumbs_down_btn)

        # Motivo do 👎 (opcional): linha discreta de chips que ocupa o lugar dos
        # botões de feedback. Clique num chip grava a chave canônica; "Outro…"
        # troca os chips por um campo curto de texto livre.
        _chip_style = """
            QPushButton {
                background: transparent;
                border: 1px solid #3f3f46;
                border-radius: 8px;
                color: #9ca3af;
                padding: 4px 10px;
                font-size: 11px;
            }
            QPushButton:hover { background: rgba(16, 185, 129, 0.12);
                                color: #10b981; border-color: #10b981; }
        """
        self._reason_container = QWidget()
        self._reason_container.setVisible(False)
        reason_layout = QHBoxLayout(self._reason_container)
        reason_layout.setContentsMargins(0, 0, 0, 0)
        reason_layout.setSpacing(6)

        self._reason_label = QLabel("O que faltou? (opcional)")
        self._reason_label.setStyleSheet("color: #6b7280; font-size: 11px;")
        reason_layout.addWidget(self._reason_label)

        self._reason_chip_btns: list[QPushButton] = []
        for text, key in self._REASON_CHIPS:
            chip = QPushButton(text)
            chip.setStyleSheet(_chip_style)
            chip.setCursor(Qt.CursorShape.PointingHandCursor)
            chip.clicked.connect(lambda _=False, k=key: self._on_reason_chosen(k))
            reason_layout.addWidget(chip)
            self._reason_chip_btns.append(chip)

        self._reason_other_btn = QPushButton("Outro…")
        self._reason_other_btn.setStyleSheet(_chip_style)
        self._reason_other_btn.setCursor(Qt.CursorShape.PointingHandCursor)
        self._reason_other_btn.setToolTip("Escrever o motivo com suas palavras")
        self._reason_other_btn.clicked.connect(self._on_reason_other)
        reason_layout.addWidget(self._reason_other_btn)
        self._reason_chip_btns.append(self._reason_other_btn)

        self._reason_edit = QLineEdit()
        self._reason_edit.setPlaceholderText("conte o motivo…")
        self._reason_edit.setMaximumWidth(220)
        self._reason_edit.setVisible(False)
        self._reason_edit.setStyleSheet("""
            QLineEdit {
                background: transparent; border: 1px solid #3f3f46;
                border-radius: 8px; color: #e5e7eb;
                padding: 4px 10px; font-size: 11px;
            }
            QLineEdit:focus { border-color: #10b981; }
        """)
        self._reason_edit.returnPressed.connect(self._on_reason_edit_confirmed)
        self._reason_edit.installEventFilter(self)  # Esc → volta aos chips
        reason_layout.addWidget(self._reason_edit)

        action_btns_layout.addWidget(self._reason_container)

        # "Responder de novo considerando isto" (Tarefa 3.8): aparece assim
        # que o motivo do 👎 é registrado — reenvia a última pergunta com o
        # motivo anexado ao prompt (consulta RAG normal, com thinking).
        self._retry_btn = QPushButton("🔁 Responder de novo considerando isto")
        self._retry_btn.setObjectName("RagRetryWithReasonButton")
        self._retry_btn.setVisible(False)
        self._retry_btn.setCursor(Qt.CursorShape.PointingHandCursor)
        self._retry_btn.setStyleSheet("""
            QPushButton {
                background: transparent;
                border: 1px solid #6366f1;
                border-radius: 8px;
                color: #818cf8;
                padding: 8px 12px;
                font-size: 12px;
            }
            QPushButton:hover { background: rgba(99, 102, 241, 0.15); color: #a5b4fc; }
            QPushButton:disabled { color: #52525b; border-color: #3f3f46; }
        """)
        self._retry_btn.clicked.connect(self._on_retry_with_reason_clicked)
        action_btns_layout.addWidget(self._retry_btn)

        chat_layout.addLayout(action_btns_layout)

        # Progress bar (visível durante geração/indexação)
        self._progress_bar = QProgressBar()
        self._progress_bar.setTextVisible(True)
        self._progress_bar.setRange(0, 0)  # indeterminate
        self._progress_bar.setFixedHeight(6)
        self._progress_bar.setVisible(False)
        chat_layout.addWidget(self._progress_bar)

        # Status da geração
        self._gen_status = QLabel("")
        self._gen_status.setVisible(False)
        chat_layout.addWidget(self._gen_status)

        # ── Input area ────────────────────────────────────────────────────────
        self._input_frame = QFrame()
        input_layout = QHBoxLayout(self._input_frame)
        input_layout.setContentsMargins(12, 8, 8, 8)
        input_layout.setSpacing(8)

        self._question_input = QLineEdit()
        self._question_input.setObjectName("ragInput")
        self._question_input.setPlaceholderText(
            "Pergunte sobre seus livros… (Enter para enviar)"
        )
        self._question_input.returnPressed.connect(self._on_send)
        input_layout.addWidget(self._question_input, stretch=1)

        self._send_btn = QPushButton("✨ Perguntar")
        self._send_btn.setObjectName("primaryBtn")
        self._send_btn.setFixedHeight(38)
        self._send_btn.setMinimumWidth(110)
        self._send_btn.setStyleSheet("""
            QPushButton#primaryBtn {
                background: qlineargradient(x1:0, y1:0, x2:1, y2:0,
                    stop:0 #059669, stop:1 #10b981);
                color: white;
                border: none;
                border-radius: 8px;
                padding: 0 16px;
                font-weight: 600;
                font-size: 13px;
            }
            QPushButton#primaryBtn:hover {
                background: qlineargradient(x1:0, y1:0, x2:1, y2:0,
                    stop:0 #10b981, stop:1 #34d399);
            }
            QPushButton#primaryBtn:pressed { background: #047857; }
            QPushButton#primaryBtn:disabled { background: #27272a; color: #52525b; }
        """)
        self._send_btn.clicked.connect(self._on_send)
        input_layout.addWidget(self._send_btn)

        self._stop_btn = QPushButton("⛔ Parar")
        self._stop_btn.setFixedHeight(38)
        self._stop_btn.setMinimumWidth(80)
        self._stop_btn.setVisible(False)
        self._stop_btn.setStyleSheet("""
            QPushButton {
                background: #3f1f1f;
                color: #f87171;
                border: 1px solid #7f1d1d;
                border-radius: 8px;
                padding: 0 12px;
                font-weight: 600;
                font-size: 13px;
            }
            QPushButton:hover { background: #7f1d1d; color: white; }
        """)
        self._stop_btn.clicked.connect(self._on_stop)
        input_layout.addWidget(self._stop_btn)

        chat_layout.addWidget(self._input_frame)
        chat_layout.setContentsMargins(24, 16, 16, 24)

        splitter.addWidget(self._chat_widget)

        # ── Painel direito: fontes e controles ─────────────────────────────────
        self._sidebar_widget = QWidget()
        self._sidebar_widget.setFixedWidth(230)
        sb_layout = QVBoxLayout(self._sidebar_widget)
        sb_layout.setContentsMargins(16, 20, 16, 20)
        sb_layout.setSpacing(16)

        # ── Seção de indexação ─────────────────────────────────────────────────
        self._idx_frame = QFrame()
        idx_layout = QVBoxLayout(self._idx_frame)
        idx_layout.setContentsMargins(12, 12, 12, 12)
        idx_layout.setSpacing(8)

        idx_title = QLabel("📚 Indexação")
        idx_title.setStyleSheet(
            "color: #10b981; font-size: 12px; font-weight: 700; letter-spacing: 0.5px;"
        )
        idx_layout.addWidget(idx_title)

        self._indexed_count_lbl = QLabel("0 chunks indexados")
        idx_layout.addWidget(self._indexed_count_lbl)

        self._index_btn = QPushButton("🔄 Reindexar Biblioteca")
        self._index_btn.clicked.connect(self._on_index_all)
        idx_layout.addWidget(self._index_btn)

        self._idx_progress_lbl = QLabel("")
        self._idx_progress_lbl.setWordWrap(True)
        self._idx_progress_lbl.setVisible(False)
        idx_layout.addWidget(self._idx_progress_lbl)

        sb_layout.addWidget(self._idx_frame)

        # ── Seletor de Modelo de IA ────────────────────────────────────────────
        self._model_frame = QFrame()
        model_layout = QVBoxLayout(self._model_frame)
        model_layout.setContentsMargins(12, 12, 12, 12)
        model_layout.setSpacing(8)

        model_title = QLabel("⚙️ Modelo de IA")
        model_title.setStyleSheet(
            "color: #6ee7b7; font-size: 12px; font-weight: 700; letter-spacing: 0.5px;"
        )
        model_layout.addWidget(model_title)

        self._model_combo = QComboBox()

        # Catálogo de modelos (tamanhos aproximados, Q4)
        self._MODEL_CATALOG = [
            ("gemma4:12b",  "Gemma 4 (12B)",  "~8 GB",   "🔥 Qualidade"),
            ("gemma4:e4b",  "Gemma 4 E4B",    "~4 GB",   "⭐ Recomendado (rápido)"),
            ("qwen2.5:7b",  "Qwen 2.5 (7B)",  "~4.7 GB", "🌍 Multilíngue + tools"),
            ("gemma3:4b",   "Gemma 3 (4B)",   "~3.3 GB", "Equilíbrio"),
            ("qwen2.5:3b",  "Qwen 2.5 (3B)",  "~1.9 GB", "🪶 Leve forte"),
            ("llama3.1:8b", "Llama 3.1 (8B)", "~4.9 GB", "Alternativo"),
            ("gemma2:2b",   "Gemma 2 (2B)",   "~1.6 GB", "🪶 Mínimo"),
        ]
        for model_id, display, size, tag in self._MODEL_CATALOG:
            self._model_combo.addItem(f"{display}  {tag}  ({size})", userData=model_id)

        self._model_combo.currentIndexChanged.connect(self._on_model_combo_changed)
        model_layout.addWidget(self._model_combo)

        self._model_badge = QLabel("🔍 Verificando...")
        self._model_badge.setStyleSheet("color: #6b7280; font-size: 10px;")
        model_layout.addWidget(self._model_badge)

        self._pull_progress = QProgressBar()
        self._pull_progress.setRange(0, 100)
        self._pull_progress.setFixedHeight(5)
        self._pull_progress.setTextVisible(False)
        self._pull_progress.setVisible(False)
        self._pull_progress.setStyleSheet("""
            QProgressBar { background: #374151; border-radius: 2px; }
            QProgressBar::chunk {
                background: qlineargradient(x1:0,y1:0,x2:1,y2:0,
                    stop:0 #10b981, stop:1 #6ee7b7);
                border-radius: 2px;
            }
        """)
        model_layout.addWidget(self._pull_progress)

        self._model_apply_btn = QPushButton("✅ Usar este Modelo")
        self._model_apply_btn.setStyleSheet("""
            QPushButton {
                background: #064e3b; color: #6ee7b7;
                border: 1px solid #065f46; border-radius: 6px;
                padding: 6px; font-size: 11px; font-weight: 600;
            }
            QPushButton:hover { background: #065f46; }
            QPushButton:disabled { background: #1f2937; color: #374151;
                                   border-color: #374151; }
        """)
        self._model_apply_btn.clicked.connect(self._on_model_apply)
        model_layout.addWidget(self._model_apply_btn)

        sb_layout.addWidget(self._model_frame)

        # ── Fontes usadas ──────────────────────────────────────────────────────
        sources_title = QLabel("📖 Fontes Consultadas")
        sources_title.setStyleSheet(
            "color: #52525b; font-size: 11px; font-weight: 700; "
            "letter-spacing: 1px; text-transform: uppercase;"
        )
        sb_layout.addWidget(sources_title)

        self._sources_list = QListWidget()
        # Fontes clicáveis (Tarefa 3.1): itens que carregam (book_id, page)
        # abrem o livro na página citada via source_clicked.
        self._sources_list.setCursor(Qt.CursorShape.PointingHandCursor)
        self._sources_list.itemClicked.connect(self._on_source_item_clicked)
        sb_layout.addWidget(self._sources_list)

        # ── Dicas ─────────────────────────────────────────────────────────────
        self._tips_frame = QFrame()
        tips_layout = QVBoxLayout(self._tips_frame)
        tips_layout.setContentsMargins(12, 10, 12, 10)
        tips_layout.setSpacing(4)
        tips_title = QLabel("💡 Dicas")
        tips_title.setStyleSheet("color: #4ade80; font-size: 11px; font-weight: 700;")
        tips_layout.addWidget(tips_title)
        self._tips_text = QLabel(
            "• Indexe sua biblioteca antes de perguntar\n"
            "• Funciona com Ollama rodando localmente\n"
            "• Modelos: bge-m3 + gemma4:e4b"
        )
        self._tips_text.setWordWrap(True)
        tips_layout.addWidget(self._tips_text)
        sb_layout.addWidget(self._tips_frame)

        sb_layout.addStretch()

        # Botão limpar chat
        self._clear_btn = QPushButton("🗑️ Limpar Conversa")
        self._clear_btn.clicked.connect(self._clear_chat)
        sb_layout.addWidget(self._clear_btn)

        splitter.addWidget(self._sidebar_widget)
        splitter.setStretchFactor(0, 1)
        splitter.setStretchFactor(1, 0)

        root.addWidget(splitter, stretch=1)

        # Padrão: sidebar recolhida (espaço morto na tela do Assistente) —
        # set_config, se chamado depois pelo MainWindow, pode reabrir com a
        # preferência persistida do usuário.
        self._apply_sidebar_collapsed(True)

        # Inicializa o visual com o tema Escuro padrão
        self.set_theme("dark")

    def set_theme(self, theme: str) -> None:
        """Aplica folha de estilos (QSS) correspondente ao tema selecionado (Claro, Sépia ou Escuro)."""
        self._current_theme = theme
        
        if theme == "light":
            # Cores do tema Claro
            bg_main = "#FFFFFF"
            bg_input = "#f4f4f5"
            border_color = "#d4d4d8"
            text_main = "#1A1A1A"
            text_sec = "#555555"
            header_gradient = "qlineargradient(x1:0, y1:0, x2:1, y2:0, stop:0 #f4f4f5, stop:1 #e4e4e7)"
            bg_sidebar = "#f4f4f5"
            border_sidebar = "1px solid #e4e4e7"
            bg_tips = "#f0fdf4"
            border_tips = "1px solid #bbf7d0"
            text_tips = "#166534"
            
        elif theme == "sepia":
            # Cores do tema Sépia
            bg_main = "#F4ECD8"
            bg_input = "#EADFCA"
            border_color = "#d4cbb8"
            text_main = "#433422"
            text_sec = "#705E4B"
            header_gradient = "qlineargradient(x1:0, y1:0, x2:1, y2:0, stop:0 #EADFCA, stop:1 #dfd8c8)"
            bg_sidebar = "#EADFCA"
            border_sidebar = "1px solid #d4cbb8"
            bg_tips = "#EADFCA"
            border_tips = "1px solid #d4cbb8"
            text_tips = "#705E4B"
            
        else: # "dark" ou fallback
            # Cores do tema Escuro
            bg_main = "#0f1115"
            bg_input = "#161920"
            border_color = "#2d333f"
            text_main = "#e5e7eb"
            text_sec = "#cbd5e1"
            header_gradient = "qlineargradient(x1:0, y1:0, x2:1, y2:0, stop:0 #161920, stop:1 #20242d)"
            bg_sidebar = "#161920"
            border_sidebar = "1px solid #2d333f"
            bg_tips = "rgba(16, 185, 129, 0.05)"
            border_tips = "1px solid rgba(16, 185, 129, 0.2)"
            text_tips = "#10b981"

        # 1. Header
        self._header.setStyleSheet(f"""
            #ragHeader {{
                background: {header_gradient};
                border-bottom: 1px solid {border_color};
                padding: 0;
            }}
        """)
        self._title_lbl.setStyleSheet(f"color: {text_main}; font-size: 15px; font-weight: 700;")
        self._sub_lbl.setStyleSheet(f"color: {text_sec}; font-size: 11px;")
        
        # 2. Chat Widget (Painel central esquerdo)
        self._chat_widget.setStyleSheet(f"background-color: {bg_main};")
        self._response_label.setStyleSheet(
            f"color: {text_sec}; font-size: 11px; font-weight: 700; "
            "letter-spacing: 1px; text-transform: uppercase;"
        )
        
        # Área de resposta (QTextEdit)
        self._response_area.setStyleSheet(f"""
            QTextEdit#responseArea {{
                background-color: {bg_input};
                border: 1px solid {border_color};
                border-radius: 12px;
                padding: 16px;
                color: {text_main};
                font-size: 14px;
                line-height: 1.6;
                selection-background-color: #10b981;
            }}
            QTextEdit#responseArea:focus {{
                border-color: #10b981;
            }}
        """)
        
        # Progress Bar e status de geração
        self._progress_bar.setStyleSheet(f"""
            QProgressBar {{
                background-color: {border_color};
                border-radius: 3px;
                max-height: 6px;
            }}
            QProgressBar::chunk {{
                background: qlineargradient(x1:0, y1:0, x2:1, y2:0,
                    stop:0 #059669, stop:1 #10b981);
                border-radius: 3px;
            }}
        """)
        self._gen_status.setStyleSheet(f"color: {text_sec}; font-size: 11px;")
        
        # Área de Input (QLineEdit e QFrame)
        self._input_frame.setStyleSheet(f"""
            QFrame {{
                background-color: {bg_input};
                border: 1px solid {border_color};
                border-radius: 12px;
            }}
            QFrame:focus-within {{
                border-color: #10b981;
            }}
        """)
        self._question_input.setStyleSheet(f"""
            QLineEdit#ragInput {{
                background: transparent;
                border: none;
                color: {text_main};
                font-size: 14px;
                padding: 6px 4px;
            }}
        """)
        
        # 3. Sidebar Widget (Painel direito de fontes e controles)
        self._sidebar_widget.setStyleSheet(f"background-color: {bg_sidebar}; border-left: {border_sidebar};")
        
        # Frame de Indexação
        self._idx_frame.setStyleSheet(f"""
            QFrame {{
                background-color: {bg_input};
                border: 1px solid {border_color};
                border-radius: 10px;
                padding: 4px;
            }}
        """)
        self._indexed_count_lbl.setStyleSheet(f"color: {text_sec}; font-size: 11px;")
        self._index_btn.setStyleSheet(f"""
            QPushButton {{
                background-color: {bg_main};
                color: #10b981;
                border: 1px solid {border_color};
                border-radius: 8px;
                padding: 8px 12px;
                font-size: 12px;
                font-weight: 600;
                text-align: left;
            }}
            QPushButton:hover {{ background-color: {bg_input}; border-color: #10b981; }}
            QPushButton:pressed {{ background-color: #047857; color: white; }}
        """)
        
        # Frame de Modelo de IA
        self._model_frame.setStyleSheet(f"""
            QFrame {{
                background-color: {bg_input};
                border: 1px solid {border_color};
                border-radius: 10px;
                padding: 4px;
            }}
        """)
        self._model_combo.setStyleSheet(f"""
            QComboBox {{
                background-color: {bg_main}; color: {text_main};
                border: 1px solid {border_color}; border-radius: 6px;
                padding: 5px 10px; font-size: 12px;
            }}
            QComboBox::drop-down {{ border: none; width: 24px; }}
            QComboBox QAbstractItemView {{
                background: {bg_main}; color: {text_main};
                border: 1px solid {border_color}; selection-background-color: {bg_input};
            }}
        """)
        
        # Lista de Fontes
        self._sources_list.setStyleSheet(f"""
            QListWidget {{
                background-color: {bg_input};
                border: 1px solid {border_color};
                border-radius: 8px;
                padding: 4px;
                color: {text_sec};
                font-size: 12px;
            }}
            QListWidget::item {{
                padding: 8px 10px;
                border-radius: 6px;
                border-bottom: 1px solid {border_color};
            }}
            QListWidget::item:hover {{ background-color: {bg_main}; color: {text_main}; }}
            QListWidget::item:selected {{ background-color: rgba(16,185,129,0.15); color: #10b981; }}
        """)
        
        # Dicas
        self._tips_frame.setStyleSheet(f"""
            QFrame {{
                background-color: {bg_tips};
                border: {border_tips};
                border-radius: 8px;
            }}
        """)
        self._tips_text.setStyleSheet(f"color: {text_tips}; font-size: 10px; line-height: 1.5;")
        
        # Botão Limpar Conversa
        self._clear_btn.setStyleSheet(f"""
            QPushButton {{
                background: transparent;
                color: {text_sec};
                border: 1px solid {border_color};
                border-radius: 8px;
                padding: 8px;
                font-size: 11px;
            }}
            QPushButton:hover {{ color: #f87171; border-color: #7f1d1d; }}
        """)

    # ── Slots públicos (chamados pelo MainWindow) ───────────────────────────────

    def set_ollama_status(self, available: bool, model: str = "") -> None:
        """Atualiza o badge de status do Ollama."""
        if available:
            self._status_badge.setText(f"🟢 Ollama · {model}")
            self._status_badge.setStyleSheet("""
                background: #052e16; color: #4ade80; border-radius: 10px;
                padding: 4px 12px; font-size: 11px; font-weight: 600;
            """)
        else:
            self._status_badge.setText("🔴 Ollama offline")
            self._status_badge.setStyleSheet("""
                background: #3f1f1f; color: #f87171; border-radius: 10px;
                padding: 4px 12px; font-size: 11px; font-weight: 600;
            """)

    def set_standalone_mode(self, is_standalone: bool) -> None:
        """Configura a visibilidade dos botões de navegação conforme o contexto."""
        self._is_standalone = is_standalone
        self._back_btn.setVisible(is_standalone)
        self._close_btn.setVisible(not is_standalone)

    def _toggle_sidebar(self) -> None:
        """Recolhe/expande a barra lateral (fontes, modelo, indexação).

        Recolhida, a área de resposta ocupa toda a largura do painel — útil no
        dock do leitor, onde o espaço é mais estreito. A escolha do usuário é
        persistida (se houver config injetada) para valer nas próximas sessões.
        """
        collapse = self._sidebar_toggle_btn.isChecked()
        self._sidebar_widget.setVisible(not collapse)
        self._sidebar_toggle_btn.setText("⟨" if collapse else "⟩")
        if self._config is not None:
            self._config.set("rag.sidebar_collapsed", collapse)

    def _apply_sidebar_collapsed(self, collapsed: bool) -> None:
        """Aplica o estado de colapso da sidebar sem disparar persistência."""
        self._sidebar_toggle_btn.setChecked(collapsed)
        self._sidebar_widget.setVisible(not collapsed)
        self._sidebar_toggle_btn.setText("⟨" if collapsed else "⟩")

    def set_config(self, config) -> None:
        """Injeta o ConfigManager para ler/persistir a preferência de sidebar.

        Chamado pelo MainWindow logo após instanciar o RAGPanel. Aplica o
        estado salvo (``rag.sidebar_collapsed``, default recolhida).
        """
        self._config = config
        collapsed = config.get("rag.sidebar_collapsed", True) if config else True
        self._apply_sidebar_collapsed(collapsed)

    def set_indexed_count(self, count: int) -> None:
        """Atualiza o contador de chunks indexados."""
        self._indexed_count_lbl.setText(f"{count:,} chunks indexados".replace(",", "."))

    def set_reading_context(self, book_id: int, title: str, page: int, text: str) -> None:
        """Guarda o contexto do que o usuário está lendo no momento."""
        # Trocar de livro zera a conversa visível (a memória por-livro continua no
        # RAGEngine). Só reseta quando o livro muda — não a cada virada de página,
        # senão apagaria a resposta enquanto o usuário navega lendo.
        prev = self._reading_context
        if prev is not None and prev.get("book_id") != book_id:
            self._reset_conversation_view()
        self._reading_context = {
            "book_id": book_id,
            "title": title,
            "page": page,
            "text": text,
        }

    def _reset_conversation_view(self) -> None:
        """Limpa a área de conversa ao trocar de livro (apenas visual)."""
        self._response_area.clear()
        self._thinking_indicator.setVisible(False)
        self._sources_list.clear()
        self._full_answer = ""
        self._question_input.clear()
        self._save_note_btn.setVisible(False)
        self._flashcard_btn.setVisible(False)
        self._hide_feedback_buttons()
        self._feedback_given = False
        self._last_feedback_id = None
        self._pending_reason = None

    def clear_reading_context(self) -> None:
        """Limpa o contexto de leitura (útil para modo standalone)."""
        self._reading_context = None

    def get_reading_context(self) -> dict | None:
        """Retorna o contexto atual de leitura, se houver."""
        return self._reading_context

    def _translation_card_colors(self) -> tuple[str, str, str, str]:
        """Paleta do cartão de tradução por tema (mesmas cores de 'dicas' do painel)."""
        theme = getattr(self, "_current_theme", "dark")
        if theme == "light":
            return "#f0fdf4", "#bbf7d0", "#166534", "#1A1A1A"
        if theme == "sepia":
            return "#EADFCA", "#d4cbb8", "#705E4B", "#433422"
        return "rgba(16, 185, 129, 0.05)", "rgba(16, 185, 129, 0.2)", "#10b981", "#e5e7eb"

    def show_translation_card(self, source_desc: str, original: str, translated: str) -> None:
        """Exibe um cartão de tradução na área de resposta do assistente.

        Substitui o antigo QMessageBox: a tradução (por seleção ou página
        inteira) aparece no mesmo painel onde o resto da conversa acontece.
        ``source_desc`` já traz a contagem de caracteres processados — é o
        "aviso do que está sendo processado" (informativo, sem diálogo).
        """
        import html as html_lib

        bg, border, header_color, body_color = self._translation_card_colors()
        header = html_lib.escape(f"🌐 Tradução — {source_desc} ({len(original)} caracteres)")
        body = html_lib.escape(translated).replace("\n", "<br>")

        cursor = self._response_area.textCursor()
        cursor.movePosition(QTextCursor.MoveOperation.End)
        self._response_area.setTextCursor(cursor)
        self._response_area.insertHtml(f"""
            <hr>
            <table width="100%" cellpadding="8" style="background-color:{bg}; border:1px solid {border};">
            <tr><td>
            <p style="color:{header_color}; font-weight:700; font-size:11px; margin:0 0 6px 0;">{header}</p>
            <p style="color:{body_color}; font-size:13px; margin:0;">{body}</p>
            </td></tr>
            </table>
            <br>
        """)
        sb = self._response_area.verticalScrollBar()
        sb.setValue(sb.maximum())

    # Marcadores que sinalizam "modelo ocupado antes do conteúdo" — dignos do
    # indicador proeminente: 💭 = raciocínio (thinking), 🧠 = preparo/troca do
    # modelo. Definidos junto com o Orchestrator (_ThinkingStatusTracker e o
    # status inicial de query_rag).
    _THINKING_MARKERS = ("💭", "🧠")

    def on_status_updated(self, status: str) -> None:
        """Atualiza o estado efêmero da geração (raciocínio/escrita).

        Vem do stream do modelo thinking via RAGWorker.status_updated; alimenta
        o pequeno label "Consultando…" e, quando o status indica que o modelo
        está pensando/carregando (💭/🧠), também o indicador PROEMINENTE acima
        da resposta — para o usuário ver que há progresso, não travamento.
        """
        if not (self._is_generating and status):
            return
        self._gen_status.setText(status)
        if status.startswith(self._THINKING_MARKERS):
            self._thinking_indicator.setText(status)
            self._thinking_indicator.setVisible(True)
        else:
            # "✍️ Escrevendo…" e afins: o conteúdo vai começar, esconde o chip.
            self._thinking_indicator.setVisible(False)

    def on_token_received(self, token: str) -> None:
        """Acrescenta um token à área de resposta (streaming)."""
        # Chegou conteúdo: a espera "invisível" acabou, oculta o indicador.
        # setVisible(False) num widget já oculto é no-op no Qt — barato por token.
        self._thinking_indicator.setVisible(False)
        cursor = self._response_area.textCursor()
        cursor.movePosition(QTextCursor.MoveOperation.End)
        self._response_area.setTextCursor(cursor)
        self._response_area.insertPlainText(token)
        # Auto-scroll para o final
        sb = self._response_area.verticalScrollBar()
        sb.setValue(sb.maximum())

    def on_answer_complete(self, full_answer: str) -> None:
        """Chamado quando a geração termina."""
        self._full_answer = full_answer
        self._set_generating(False)

        # Fontes clicáveis (Tarefa 3.1): enriquece a lista com as citações
        # [Título, p. X] presentes na resposta, resolvidas para book_id.
        self._augment_sources_with_citations(full_answer)

        # Human-in-the-loop: Mostrar botão de salvar anotação se houver contexto de livro
        is_global = getattr(self, "_is_standalone", False)
        if self._reading_context and not is_global and self._reading_context.get("book_id", 0) > 0 and full_answer.strip():
            self._save_note_btn.setText("💾 Salvar como Anotação")
            self._save_note_btn.setEnabled(True)
            self._save_note_btn.setVisible(True)
            self._flashcard_btn.setVisible(True)
        elif full_answer.strip():
            # Mesmo fora do contexto, deixa criar flashcard livre
            self._flashcard_btn.setVisible(True)

        # Feedback 👍/👎: disponível em qualquer resposta não vazia (livro ou global).
        if full_answer.strip():
            self._show_feedback_buttons()

    def _show_feedback_buttons(self) -> None:
        for btn, label in (
            (self._thumbs_up_btn, "👍 Útil"),
            (self._thumbs_down_btn, "👎 Não ajudou"),
        ):
            btn.setText(label)
            btn.setEnabled(True)
            btn.setVisible(True)

    def _hide_feedback_buttons(self) -> None:
        self._thumbs_up_btn.setVisible(False)
        self._thumbs_down_btn.setVisible(False)
        self._retry_btn.setVisible(False)
        self._hide_reason_chips()

    def _on_feedback_clicked(self, rating: int) -> None:
        """Registra 👍 (+1) / 👎 (-1) da resposta atual. Um voto por resposta.

        👍: confirmação imediata ("✅ Obrigado!"), zero fricção. 👎: o voto é
        emitido/persistido na hora; em seguida os botões dão lugar a uma linha
        discreta de chips para capturar o motivo (opcional).
        """
        if self._feedback_given:
            return
        self._feedback_given = True
        # Voto novo: zera qualquer estado de motivo herdado.
        self._last_feedback_id = None
        self._pending_reason = None
        self._last_reason_for_retry = None
        ctx = self._reading_context or {}
        book_id = ctx.get("book_id") or None
        if book_id == 0:
            book_id = None
        context = {
            "kind": "answer",
            "book_id": book_id,
            "page": ctx.get("page"),
            "session_id": self._current_session_id,
            "query": self._last_query,
        }
        self.feedback_submitted.emit(rating, context)
        self._thumbs_up_btn.setEnabled(False)
        self._thumbs_down_btn.setEnabled(False)
        if rating > 0:
            # 👍 — confirmação imediata no mesmo lugar de hoje.
            self._thumbs_up_btn.setText("✅ Obrigado!")
        else:
            # 👎 — voto já emitido; abre os chips de motivo (opcional).
            self._thumbs_up_btn.setVisible(False)
            self._thumbs_down_btn.setVisible(False)
            self._show_reason_chips()

    # ── Motivo do 👎 (chips) ────────────────────────────────────────────────────

    def on_feedback_persisted(self, feedback_id: int) -> None:
        """Recebe o id da linha persistida em agent_feedback (via MainWindow).

        Habilita o envio do motivo. Se o usuário já escolheu um motivo antes do
        id chegar, emite-o agora (ADR-005 — persistência é rápida, mas defensivo).
        """
        self._last_feedback_id = feedback_id
        if self._pending_reason is not None:
            reason = self._pending_reason
            self._pending_reason = None
            self.feedback_reason_submitted.emit(feedback_id, reason)

    def _show_reason_chips(self) -> None:
        """Exibe a linha de chips de motivo no lugar dos botões de feedback."""
        self._reason_edit.setVisible(False)
        self._reason_edit.clear()
        self._reason_label.setVisible(True)
        for chip in self._reason_chip_btns:
            chip.setVisible(True)
        self._reason_container.setVisible(True)

    def _hide_reason_chips(self) -> None:
        """Esconde toda a área de motivo (chips + campo livre)."""
        self._reason_edit.clear()
        self._reason_edit.setVisible(False)
        self._reason_container.setVisible(False)

    def _on_reason_other(self) -> None:
        """'Outro…': troca os chips por um campo curto de texto livre."""
        self._reason_label.setVisible(False)
        for chip in self._reason_chip_btns:
            chip.setVisible(False)
        self._reason_edit.setVisible(True)
        self._reason_edit.setFocus()

    def _cancel_reason_other(self) -> None:
        """Esc no campo livre: descarta o texto e volta aos chips."""
        self._reason_edit.clear()
        self._reason_edit.setVisible(False)
        self._reason_label.setVisible(True)
        for chip in self._reason_chip_btns:
            chip.setVisible(True)

    def _on_reason_edit_confirmed(self) -> None:
        """Enter no campo livre: grava o texto cru como motivo."""
        text = self._reason_edit.text().strip()
        if not text:
            return
        self._submit_reason(text)

    def _on_reason_chosen(self, key: str) -> None:
        """Clique num chip: grava a chave canônica como motivo."""
        self._submit_reason(key)

    def _submit_reason(self, reason: str) -> None:
        """Emite o motivo (se o id já chegou) ou o guarda para quando chegar,
        esconde os chips e confirma visualmente ("✅ Obrigado!").

        Tarefa 3.8: também libera o botão "Responder de novo considerando
        isto" — motivo registrado é o gatilho para reenviar a última
        pergunta com essa instrução extra.
        """
        self._hide_reason_chips()
        if self._last_feedback_id is not None:
            self.feedback_reason_submitted.emit(self._last_feedback_id, reason)
        else:
            # Persistência ainda não confirmou o id — guarda para emitir depois.
            self._pending_reason = reason
        # Confirmação visual no mesmo lugar de hoje.
        self._thumbs_down_btn.setText("✅ Obrigado!")
        self._thumbs_down_btn.setEnabled(False)
        self._thumbs_down_btn.setVisible(True)
        self._last_reason_for_retry = reason
        self._retry_btn.setEnabled(True)
        self._retry_btn.setVisible(True)

    def eventFilter(self, obj, event):  # noqa: N802 (assinatura do Qt)
        """Esc no campo de texto livre volta aos chips (sem perder o voto)."""
        if (
            obj is self._reason_edit
            and event.type() == QEvent.Type.KeyPress
            and event.key() == Qt.Key.Key_Escape
        ):
            self._cancel_reason_other()
            return True
        return super().eventFilter(obj, event)

    def _on_flashcard_clicked(self) -> None:
        """Abre o dialog para criar um flashcard a partir da resposta e do contexto."""
        if not self._full_answer.strip():
            return
            
        front = self._reading_context.get("text", "Nova Pergunta") if self._reading_context else "Nova Pergunta"
        back = self._full_answer.strip()
        
        # O _rag_panel reporta para a MainWindow, precisamos enviar um sinal.
        # Mas para simplificar, usaremos o MainWindow parent ou um custom event.
        # Vamos achar a main_window recursivamente ou adicionar um signal:
        parent = self.parent()
        while parent:
            if hasattr(parent, "_open_anki_export_dialog"):
                parent._open_anki_export_dialog(front, back)
                return
            parent = parent.parent()

    def _on_save_note_clicked(self) -> None:
        """Chamado quando o usuário clica para salvar a resposta como anotação."""
        if not self._reading_context or not self._full_answer.strip():
            return
            
        book_id = self._reading_context["book_id"]
        page = self._reading_context["page"]
        content = self._full_answer.strip()
        
        # Feedback visual imediato
        self._save_note_btn.setText("✅ Salvo!")
        self._save_note_btn.setEnabled(False)
        
        # Emite sinal para o MainWindow persistir no banco
        self.save_annotation_requested.emit(book_id, page, content)

    def set_books_provider(self, provider) -> None:
        """Define o provedor da lista de livros (``db.get_all_books``).

        Usado para resolver as citações ``[Título, p. X]`` da resposta em
        ``book_id`` (Tarefa 3.1). Sem provedor, a lista de fontes ainda funciona
        a partir dos metadados dos trechos recuperados (que já trazem book_id).
        """
        self._books_provider = provider

    def on_sources_found(self, sources: list) -> None:
        """Popula o painel de fontes consultadas.

        Cada trecho recuperado já traz ``book_id`` e ``page_number`` (0-based) nos
        metadados — guardamos ``(book_id, page)`` no item para torná-lo clicável
        (Tarefa 3.1). Itens sem esses dados ficam informativos (não clicáveis).
        """
        self._sources_list.clear()
        for src in sources:
            meta = src.get("metadata", {})
            title = meta.get("title", "Desconhecido")
            author = meta.get("author", "")
            dist = src.get("distance", 0.0)
            similarity = max(0, round((1 - dist) * 100))
            book_id = meta.get("book_id")
            page = meta.get("page_number")
            text = f"📖 {title}"
            if author:
                text += f"\n    {author}"
            if book_id is not None and page is not None:
                text += f"\n    p. {int(page) + 1} · {similarity}% relevante"
            else:
                text += f"\n    {similarity}% relevante"
            item = QListWidgetItem(text)
            item.setToolTip(src.get("document", "")[:200] + "…")
            self._tag_source_item(item, book_id, page)
            self._sources_list.addItem(item)

    def _tag_source_item(self, item, book_id, page) -> None:
        """Marca o item com ``(book_id, page0)`` se ambos existirem — clicável."""
        if book_id is None or page is None:
            return
        page0 = max(0, int(page))
        item.setData(Qt.ItemDataRole.UserRole, (int(book_id), page0))
        item.setToolTip("Clique para abrir na fonte · " + (item.toolTip() or ""))

    def _augment_sources_with_citations(self, answer: str) -> None:
        """Acrescenta à lista de fontes as citações ``[Título, p. X]`` da resposta.

        Resolve o título → book_id via fuzzy match (``resolve_citation``) contra os
        livros do banco. Só adiciona pares ``(book_id, page)`` ainda não presentes
        (dedup com os trechos recuperados). Título não resolvido → ignorado
        (degradação graciosa, ADR-005).
        """
        if not answer or not answer.strip() or self._books_provider is None:
            return
        from src.core.rag.source_citations import parse_citations, resolve_citation

        citations = parse_citations(answer)
        if not citations:
            return
        try:
            books = self._books_provider() or []
        except Exception:
            books = []
        if not books:
            return

        existing: set[tuple[int, int]] = set()
        for i in range(self._sources_list.count()):
            data = self._sources_list.item(i).data(Qt.ItemDataRole.UserRole)
            if isinstance(data, tuple):
                existing.add(data)

        for cit in citations:
            book_id, page1 = resolve_citation(cit, books)
            if book_id is None:
                continue
            page0 = max(0, int(page1) - 1)  # citação é 1-based; leitor é 0-based
            key = (int(book_id), page0)
            if key in existing:
                continue
            existing.add(key)
            item = QListWidgetItem(f"🔖 {cit.title} · p. {page1}")
            item.setData(Qt.ItemDataRole.UserRole, key)
            item.setToolTip("Citação da resposta · clique para abrir")
            self._sources_list.addItem(item)

    def _on_source_item_clicked(self, item) -> None:
        """Emite ``source_clicked`` se o item carregar ``(book_id, page0)``."""
        data = item.data(Qt.ItemDataRole.UserRole) if item else None
        if isinstance(data, tuple) and len(data) == 2:
            self.source_clicked.emit(int(data[0]), int(data[1]))

    def on_progress_updated(self, current: int, total: int, message: str) -> None:
        """Atualiza o progresso da indexação."""
        self._idx_progress_lbl.setText(message)
        self._idx_progress_lbl.setVisible(True)
        if total > 0:
            self._progress_bar.setRange(0, total)
            self._progress_bar.setValue(current)
        else:
            self._progress_bar.setRange(0, 0)

    def on_error(self, message: str) -> None:
        """Exibe erro na área de resposta."""
        self._response_area.setPlainText(f"⚠️ Erro: {message}")
        self._set_generating(False)
        self._set_indexing(False)

    def on_indexing_complete(self) -> None:
        """Chamado quando a indexação termina."""
        self._set_indexing(False)
        self._idx_progress_lbl.setVisible(False)

    # ── Handlers internos ──────────────────────────────────────────────────────

    def _on_send(self) -> None:
        question = self._question_input.text().strip()
        if not question or self._is_generating:
            return
        self._begin_new_query(question)
        self.query_requested.emit(question)

    def _begin_new_query(self, question: str) -> None:
        """Prepara a UI para uma nova pergunta (limpa resposta, reinicia o
        estado de feedback/sessão). Usado pelo envio normal (_on_send) e
        pelo reenvio com motivo (3.8, _on_retry_with_reason_clicked) — as
        duas entradas de uma nova rodada de consulta."""
        self._response_area.clear()
        self._sources_list.clear()
        self._set_generating(True)
        self._save_note_btn.setVisible(False)
        # Nova pergunta: nova sessão de feedback (1 voto por resposta).
        self._last_query = question
        self._current_session_id = str(uuid.uuid4())
        self._feedback_given = False
        self._last_feedback_id = None
        self._pending_reason = None
        self._gen_status.setText(f'🔍 Consultando: "{question[:60]}..."')

    def _on_retry_with_reason_clicked(self) -> None:
        """'Responder de novo considerando isto' (3.8): reenvia a ÚLTIMA
        pergunta com o motivo do 👎 anexado. A augmentação do prompt fica a
        cargo do MainWindow (retry_with_reason_requested); aqui só prepara a
        UI como uma consulta nova e emite a query original + o motivo."""
        query = self._last_query
        reason = self._last_reason_for_retry
        if not query or not reason or self._is_generating:
            return
        self._begin_new_query(query)
        self.retry_with_reason_requested.emit(query, reason)

    def _on_stop(self) -> None:
        self.stop_requested.emit()
        self._set_generating(False)

    def _on_index_all(self) -> None:
        self._set_indexing(True)
        self._idx_progress_lbl.setText("Iniciando indexação…")
        self._idx_progress_lbl.setVisible(True)
        self.index_requested.emit()

    def _clear_chat(self) -> None:
        self._response_area.clear()
        self._thinking_indicator.setVisible(False)
        self._sources_list.clear()
        self._full_answer = ""
        self._question_input.clear()
        self._question_input.setFocus()
        self.clear_chat_requested.emit()

    def _set_generating(self, active: bool) -> None:
        self._is_generating = active
        self._send_btn.setVisible(not active)
        self._stop_btn.setVisible(active)
        self._progress_bar.setVisible(active)
        self._gen_status.setVisible(active)
        self._question_input.setEnabled(not active)
        # Indicador de raciocínio: começa oculto e só reaparece quando um status
        # 💭/🧠 chega (on_status_updated). Ao terminar/parar, some.
        self._thinking_indicator.setVisible(False)
        if active:
            self._save_note_btn.setVisible(False)
            self._flashcard_btn.setVisible(False)
            self._hide_feedback_buttons()
        else:
            self._gen_status.setText("")

    def _set_indexing(self, active: bool) -> None:
        self._index_btn.setEnabled(not active)
        self._progress_bar.setVisible(active)
        if active:
            self._progress_bar.setRange(0, 0)
        else:
            self._progress_bar.setRange(0, 1)
            self._progress_bar.setValue(1)

    # ── Seletor de Modelos ─────────────────────────────────────────────────────

    def update_model_list(self, installed_names: list[str]) -> None:
        """Atualiza badges indicando quais modelos estão instalados.

        Args:
            installed_names: Lista de nomes de modelos disponíveis no Ollama.
        """
        self._installed_models = set(installed_names)
        self._on_model_combo_changed(self._model_combo.currentIndex())

    def _on_model_combo_changed(self, index: int) -> None:
        """Atualiza o badge e o botão conforme o modelo selecionado."""
        if index < 0 or index >= len(self._MODEL_CATALOG):
            return
        model_id = self._MODEL_CATALOG[index][0]
        installed = getattr(self, "_installed_models", set())

        if model_id in installed:
            self._model_badge.setText("✅ Instalado")
            self._model_badge.setStyleSheet("color: #4ade80; font-size: 10px; font-weight: 600;")
            self._model_apply_btn.setText("✅ Usar este Modelo")
        else:
            self._model_badge.setText("⬇️  Não instalado")
            self._model_badge.setStyleSheet("color: #f59e0b; font-size: 10px; font-weight: 600;")
            self._model_apply_btn.setText("⬇️  Baixar e Usar Modelo")

    def _on_model_apply(self) -> None:
        """Aplica o modelo selecionado ou inicia o pull se não instalado."""
        idx = self._model_combo.currentIndex()
        if idx < 0:
            return
        model_id = self._MODEL_CATALOG[idx][0]
        installed = getattr(self, "_installed_models", set())

        if model_id in installed:
            # Aplica imediatamente
            self.model_changed.emit(model_id)
            self._model_badge.setText(f"🟢 Usando: {model_id}")
        else:
            # Inicia pull via worker
            self._start_model_pull(model_id)

    def _start_model_pull(self, model_id: str) -> None:
        """Inicia o download do modelo via ModelPullWorker."""
        from src.gui.workers.pull_worker import ModelPullWorker

        if hasattr(self, "_pull_worker") and self._pull_worker and self._pull_worker.isRunning():
            return

        ollama_url = "http://localhost:11434"
        self._pull_worker = ModelPullWorker(ollama_url, model_id)
        self._pull_worker.progress_updated.connect(self._on_pull_progress)
        self._pull_worker.pull_complete.connect(self._on_pull_complete)
        self._pull_worker.error_occurred.connect(
            lambda err: self._model_badge.setText(f"❌ Erro: {err[:40]}")
        )

        self._pull_progress.setVisible(True)
        self._pull_progress.setRange(0, 100)
        self._model_apply_btn.setEnabled(False)
        self._model_badge.setText(f"⬇️ Baixando {model_id}…")
        self._pull_worker.start()

    def _on_pull_progress(self, completed: int, total: int, status: str) -> None:
        if total > 0:
            pct = int(completed / total * 100)
            self._pull_progress.setValue(pct)
            mb_done = completed / 1_048_576
            mb_total = total / 1_048_576
            self._model_badge.setText(f"⬇️  {mb_done:.0f} / {mb_total:.0f} MB")
        else:
            self._model_badge.setText(f"⬇️  {status}")

    def _on_pull_complete(self, success: bool, model_id: str) -> None:
        self._pull_progress.setVisible(False)
        self._model_apply_btn.setEnabled(True)

        if success:
            if not hasattr(self, "_installed_models"):
                self._installed_models = set()
            self._installed_models.add(model_id)
            self._model_badge.setText("✅ Instalado")
            self._model_badge.setStyleSheet("color: #4ade80; font-size: 10px; font-weight: 600;")
            self._model_apply_btn.setText("✅ Usar este Modelo")
            self.model_changed.emit(model_id)
        else:
            self._model_badge.setText("❌ Falha no download")
            self._model_badge.setStyleSheet("color: #f87171; font-size: 10px;")

