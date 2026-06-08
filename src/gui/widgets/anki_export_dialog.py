from PyQt6.QtWidgets import (
    QDialog, QVBoxLayout, QHBoxLayout, QLabel, 
    QPushButton, QTextEdit, QComboBox, QMessageBox
)
from PyQt6.QtCore import Qt
from PyQt6.QtGui import QIcon

class AnkiExportDialog(QDialog):
    """
    Diálogo de Preview e Edição para criar um Flashcard (Frente e Verso)
    e enviá-lo ao Anki.
    """
    def __init__(self, service, initial_front: str = "", initial_back: str = "", parent=None):
        super().__init__(parent)
        self.service = service
        self.setWindowTitle("Exportar para o Anki")
        self.resize(500, 400)
        self.setModal(True)
        
        self.initial_front = initial_front
        self.initial_back = initial_back
        
        self.result_deck = "Default"
        self.result_front = ""
        self.result_back = ""
        self.saved = False
        
        self._setup_ui()
        self._load_decks()

    def _setup_ui(self):
        layout = QVBoxLayout(self)
        layout.setSpacing(12)
        
        # Header: Deck selection
        header_layout = QHBoxLayout()
        deck_label = QLabel("Deck:")
        deck_label.setStyleSheet("font-weight: bold;")
        self.deck_combo = QComboBox()
        self.deck_combo.addItem("Default")
        header_layout.addWidget(deck_label)
        header_layout.addWidget(self.deck_combo, stretch=1)
        layout.addLayout(header_layout)
        
        # Front
        front_label = QLabel("Frente (Pergunta / Gatilho):")
        front_label.setStyleSheet("font-weight: bold; color: #059669;")
        layout.addWidget(front_label)
        
        self.front_edit = QTextEdit()
        self.front_edit.setPlainText(self.initial_front)
        self.front_edit.setMinimumHeight(80)
        layout.addWidget(self.front_edit)
        
        # Back
        back_label = QLabel("Verso (Resposta / Explicação):")
        back_label.setStyleSheet("font-weight: bold; color: #2563eb;")
        layout.addWidget(back_label)
        
        self.back_edit = QTextEdit()
        self.back_edit.setPlainText(self.initial_back)
        self.back_edit.setMinimumHeight(120)
        layout.addWidget(self.back_edit)
        
        # Status / Info
        self.status_label = QLabel()
        self.status_label.setStyleSheet("color: #64748b; font-size: 11px;")
        layout.addWidget(self.status_label)
        
        # Buttons
        btn_layout = QHBoxLayout()
        self.cancel_btn = QPushButton("Cancelar")
        self.cancel_btn.clicked.connect(self.reject)
        
        self.save_btn = QPushButton("💾 Salvar no Anki")
        self.save_btn.setStyleSheet("""
            QPushButton {
                background-color: #10b981;
                color: white;
                font-weight: bold;
                padding: 6px 12px;
                border-radius: 4px;
                border: none;
            }
            QPushButton:hover { background-color: #059669; }
            QPushButton:disabled { background-color: #94a3b8; }
        """)
        self.save_btn.clicked.connect(self._on_save)
        
        btn_layout.addStretch()
        btn_layout.addWidget(self.cancel_btn)
        btn_layout.addWidget(self.save_btn)
        layout.addLayout(btn_layout)

    def _load_decks(self):
        """Carrega a lista de decks disponíveis do AnkiConnect."""
        self.status_label.setText("Verificando conexão com o AnkiConnect...")
        
        # Para evitar travar a UI se o Anki estiver offline, faremos sincrono rápido (timeout 3s)
        # Em produção ideal seria num QThread, mas para carregar o combo rápido e falhar rápido:
        try:
            if self.service.is_available():
                decks = self.service.get_deck_names()
                if decks:
                    self.deck_combo.clear()
                    self.deck_combo.addItems(decks)
                self.status_label.setText("Anki conectado. Selecione o deck.")
                self.status_label.setStyleSheet("color: #059669; font-size: 11px;")
            else:
                self.status_label.setText("Anki fechado. O card será salvo na fila local de exportação.")
                self.status_label.setStyleSheet("color: #d97706; font-size: 11px;")
        except Exception as e:
            self.status_label.setText(f"Erro ao conectar: {e}")

    def _on_save(self):
        front = self.front_edit.toPlainText().strip()
        back = self.back_edit.toPlainText().strip()
        
        if not front or not back:
            QMessageBox.warning(self, "Aviso", "A frente e o verso não podem estar vazios.")
            return
            
        self.result_deck = self.deck_combo.currentText()
        self.result_front = front
        self.result_back = back
        self.saved = True
        self.accept()
