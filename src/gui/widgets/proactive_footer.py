from PyQt6.QtWidgets import QWidget, QHBoxLayout, QVBoxLayout, QLabel, QPushButton
from PyQt6.QtCore import Qt, pyqtSignal

class ProactiveFooterWidget(QWidget):
    closed = pyqtSignal()
    flashcard_requested = pyqtSignal(str)
    
    def __init__(self, parent=None):
        super().__init__(parent)
        self.setVisible(False)
        self._setup_ui()
        
    def _setup_ui(self):
        self.setObjectName("ProactiveFooter")
        self.setMinimumHeight(80)
        self.setMaximumHeight(150)
        
        main_layout = QHBoxLayout(self)
        main_layout.setContentsMargins(16, 12, 16, 12)
        main_layout.setSpacing(12)
        
        # Ícone ou indicador visual
        self.icon_label = QLabel("💡")
        self.icon_label.setStyleSheet("font-size: 20px; padding-top: 2px;")
        self.icon_label.setAlignment(Qt.AlignmentFlag.AlignTop)
        main_layout.addWidget(self.icon_label)
        
        # Container de texto
        text_container = QWidget()
        text_layout = QVBoxLayout(text_container)
        text_layout.setContentsMargins(0, 0, 0, 0)
        text_layout.setSpacing(4)
        
        # Header: Tipo + Confiança
        self.header_label = QLabel()
        self.header_label.setStyleSheet("font-size: 11px; font-weight: bold; color: #10b981;")
        text_layout.addWidget(self.header_label)
        
        # Corpo da observação
        self.body_label = QLabel()
        self.body_label.setWordWrap(True)
        self.body_label.setStyleSheet("font-size: 13px; color: #e5e7eb; line-height: 1.4;")
        text_layout.addWidget(self.body_label)
        text_layout.addStretch()
        
        main_layout.addWidget(text_container, stretch=1)
        
        # Botão fechar
        close_btn = QPushButton("✕")
        close_btn.setFixedSize(24, 24)
        close_btn.setStyleSheet("""
            QPushButton { background: transparent; border: none; color: #9ca3af; font-weight: bold; }
            QPushButton:hover { color: #f3f4f6; background: #374151; border-radius: 4px; }
        """)
        close_btn.clicked.connect(self.hide)
        close_btn.clicked.connect(self.closed.emit)
        
        # Botão Flashcard
        self.flashcard_btn = QPushButton("🃏 Criar Flashcard")
        self.flashcard_btn.setStyleSheet("""
            QPushButton { background-color: #2563eb; color: white; padding: 4px 8px; border-radius: 4px; border: none; font-size: 11px; }
            QPushButton:hover { background-color: #1d4ed8; }
        """)
        self.flashcard_btn.clicked.connect(lambda: self.flashcard_requested.emit(self.body_label.text()))
        
        btn_layout = QVBoxLayout()
        btn_layout.addWidget(close_btn)
        btn_layout.addWidget(self.flashcard_btn)
        btn_layout.addStretch()
        main_layout.addLayout(btn_layout)
        
    def set_observation(self, obs: dict):
        tipo = obs.get("tipo", "Observação")
        confianca = obs.get("confianca", "Média")
        texto = obs.get("texto", "")
        
        self.header_label.setText(f"{tipo.upper()} • CONFIANÇA {confianca.upper()}")
        self.body_label.setText(texto)
        self.setVisible(True)
        
    def set_theme(self, theme: str):
        if theme == "light":
            self.setStyleSheet("""
                #ProactiveFooter {
                    background-color: #f8fafc;
                    border-top: 1px solid #e2e8f0;
                }
            """)
            self.header_label.setStyleSheet("font-size: 11px; font-weight: bold; color: #059669;")
            self.body_label.setStyleSheet("font-size: 13px; color: #1e293b; line-height: 1.4;")
        elif theme == "sepia":
            self.setStyleSheet("""
                #ProactiveFooter {
                    background-color: #f1e7d0;
                    border-top: 1px solid #d4c5b0;
                }
            """)
            self.header_label.setStyleSheet("font-size: 11px; font-weight: bold; color: #b45309;")
            self.body_label.setStyleSheet("font-size: 13px; color: #45301f; line-height: 1.4;")
        else: # dark
            self.setStyleSheet("""
                #ProactiveFooter {
                    background-color: #1e293b;
                    border-top: 1px solid #334155;
                }
            """)
            self.header_label.setStyleSheet("font-size: 11px; font-weight: bold; color: #10b981;")
            self.body_label.setStyleSheet("font-size: 13px; color: #e5e7eb; line-height: 1.4;")
