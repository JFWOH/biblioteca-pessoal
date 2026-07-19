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
        # Sem este atributo, QWidget SUBCLASSE não pinta background vindo de
        # QSS (#ProactiveFooter { background-color } seria regra morta) —
        # mesma lição do AnnotationPanel (Onda 0b 1/2, PR #42/#43).
        self.setAttribute(Qt.WidgetAttribute.WA_StyledBackground, True)
        self.setMinimumHeight(80)
        self.setMaximumHeight(150)

        main_layout = QHBoxLayout(self)
        main_layout.setContentsMargins(16, 12, 16, 12)
        main_layout.setSpacing(12)

        # Ícone ou indicador visual
        self.icon_label = QLabel("💡")
        self.icon_label.setObjectName("proactiveFooterIcon")
        self.icon_label.setAlignment(Qt.AlignmentFlag.AlignTop)
        main_layout.addWidget(self.icon_label)

        # Container de texto
        text_container = QWidget()
        text_layout = QVBoxLayout(text_container)
        text_layout.setContentsMargins(0, 0, 0, 0)
        text_layout.setSpacing(4)

        # Header: Tipo + Confiança
        self.header_label = QLabel()
        self.header_label.setObjectName("proactiveFooterHeader")
        text_layout.addWidget(self.header_label)

        # Corpo da observação
        self.body_label = QLabel()
        self.body_label.setWordWrap(True)
        self.body_label.setObjectName("proactiveFooterBody")
        text_layout.addWidget(self.body_label)
        text_layout.addStretch()

        main_layout.addWidget(text_container, stretch=1)

        # Botão fechar
        close_btn = QPushButton("✕")
        close_btn.setFixedSize(24, 24)
        close_btn.setObjectName("proactiveFooterCloseBtn")
        close_btn.clicked.connect(self.hide)
        close_btn.clicked.connect(self.closed.emit)

        # Botão Flashcard
        self.flashcard_btn = QPushButton("🃏 Criar Flashcard")
        self.flashcard_btn.setObjectName("proactiveFooterFlashcardBtn")
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
        
