"""Painel de chat RAG integrado ao MainWindow.

Widget premium com chat de IA local, streaming de respostas, exibição de
fontes bibliográficas e controle de indexação — tudo rodando localmente.
"""

from __future__ import annotations

from PyQt6.QtCore import Qt, QTimer, pyqtSignal
from PyQt6.QtGui import QFont, QColor, QTextCharFormat, QTextCursor
from PyQt6.QtWidgets import (
    QWidget, QVBoxLayout, QHBoxLayout, QLabel, QLineEdit,
    QPushButton, QTextEdit, QListWidget, QListWidgetItem,
    QProgressBar, QFrame, QSizePolicy, QSplitter, QScrollArea,
    QComboBox,
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

    def __init__(self, parent=None) -> None:
        super().__init__(parent)
        self._is_generating = False
        self._full_answer = ""
        self._reading_context = None
        self._is_standalone = False
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
        dock do leitor, onde o espaço é mais estreito.
        """
        collapse = self._sidebar_toggle_btn.isChecked()
        self._sidebar_widget.setVisible(not collapse)
        self._sidebar_toggle_btn.setText("⟨" if collapse else "⟩")

    def set_indexed_count(self, count: int) -> None:
        """Atualiza o contador de chunks indexados."""
        self._indexed_count_lbl.setText(f"{count:,} chunks indexados".replace(",", "."))

    def set_reading_context(self, book_id: int, title: str, page: int, text: str) -> None:
        """Guarda o contexto do que o usuário está lendo no momento."""
        self._reading_context = {
            "book_id": book_id,
            "title": title,
            "page": page,
            "text": text,
        }

    def clear_reading_context(self) -> None:
        """Limpa o contexto de leitura (útil para modo standalone)."""
        self._reading_context = None

    def get_reading_context(self) -> dict | None:
        """Retorna o contexto atual de leitura, se houver."""
        return self._reading_context

    def on_token_received(self, token: str) -> None:
        """Acrescenta um token à área de resposta (streaming)."""
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

    def _on_flashcard_clicked(self) -> None:
        """Abre o dialog para criar um flashcard a partir da resposta e do contexto."""
        if not self._full_answer.strip():
            return
            
        front = self._reading_context.get("text", "Nova Pergunta") if self._reading_context else "Nova Pergunta"
        back = self._full_answer.strip()
        
        # O _rag_panel reporta para a MainWindow, precisamos enviar um sinal.
        # Mas para simplificar, usaremos o MainWindow parent ou um custom event.
        # Vamos achar a main_window recursivamente ou adicionar um signal:
        from PyQt6.QtWidgets import QWidget
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

    def on_sources_found(self, sources: list) -> None:
        """Popula o painel de fontes consultadas."""
        self._sources_list.clear()
        for src in sources:
            meta = src.get("metadata", {})
            title = meta.get("title", "Desconhecido")
            author = meta.get("author", "")
            dist = src.get("distance", 0.0)
            similarity = max(0, round((1 - dist) * 100))
            text = f"📖 {title}"
            if author:
                text += f"\n    {author}"
            text += f"\n    {similarity}% relevante"
            item = QListWidgetItem(text)
            item.setToolTip(src.get("document", "")[:200] + "…")
            self._sources_list.addItem(item)

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
        self._response_area.clear()
        self._sources_list.clear()
        self._set_generating(True)
        self._save_note_btn.setVisible(False)
        self._gen_status.setText(f'🔍 Consultando: "{question[:60]}..."')
        self.query_requested.emit(question)

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
        if active:
            self._save_note_btn.setVisible(False)
            self._flashcard_btn.setVisible(False)
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

