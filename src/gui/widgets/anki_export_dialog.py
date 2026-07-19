from PyQt6.QtWidgets import (
    QDialog, QVBoxLayout, QHBoxLayout, QLabel,
    QPushButton, QTextEdit, QComboBox, QMessageBox
)

from src.gui.styles import emoji_icon

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
        deck_label.setObjectName("ankiDeckLabel")
        self.deck_combo = QComboBox()
        self.deck_combo.addItem("Default")
        header_layout.addWidget(deck_label)
        header_layout.addWidget(self.deck_combo, stretch=1)
        layout.addLayout(header_layout)
        
        # Front
        front_label = QLabel("Frente (Pergunta / Gatilho):")
        front_label.setObjectName("ankiFrontLabel")
        layout.addWidget(front_label)
        
        self.front_edit = QTextEdit()
        self.front_edit.setPlainText(self.initial_front)
        self.front_edit.setMinimumHeight(80)
        layout.addWidget(self.front_edit)
        
        # Back
        back_label = QLabel("Verso (Resposta / Explicação):")
        back_label.setObjectName("ankiBackLabel")
        layout.addWidget(back_label)
        
        self.back_edit = QTextEdit()
        self.back_edit.setPlainText(self.initial_back)
        self.back_edit.setMinimumHeight(120)
        layout.addWidget(self.back_edit)
        
        # Status / Info
        self.status_label = QLabel()
        self.status_label.setObjectName("ankiStatusChecking")
        layout.addWidget(self.status_label)

        # Reenvio da fila de fallback (só aparece quando há pendências e o Anki está online)
        self.flush_btn = QPushButton()
        self.flush_btn.setIcon(emoji_icon("↩️", 14))
        self.flush_btn.setVisible(False)
        self.flush_btn.clicked.connect(self._on_flush_pending)
        layout.addWidget(self.flush_btn)
        
        # Buttons
        btn_layout = QHBoxLayout()
        self.cancel_btn = QPushButton("Cancelar")
        self.cancel_btn.clicked.connect(self.reject)
        
        self.save_btn = QPushButton("Salvar no Anki")
        self.save_btn.setIcon(emoji_icon("💾"))
        self.save_btn.setObjectName("ankiSaveBtn")
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
                self._set_status_style("ankiStatusConnected")
                self._refresh_pending_button()
            else:
                self.status_label.setText("Anki fechado. O card será salvo na fila local de exportação.")
                self._set_status_style("ankiStatusOffline")
        except Exception as e:
            self.status_label.setText(f"Erro ao conectar: {e}")

    def _set_status_style(self, object_name: str) -> None:
        """Troca o objectName do status (estado dinâmico). Delegado ao helper
        compartilhado ``styles.swap_object_name``."""
        from src.gui.styles import swap_object_name
        swap_object_name(self.status_label, object_name)

    def _refresh_pending_button(self):
        """Mostra o botão de reenvio se houver notas na fila de fallback."""
        try:
            pending = self.service.count_pending_fallback()
        except Exception:
            pending = 0
        if pending > 0:
            self.flush_btn.setText(f"Reenviar {pending} flashcard(s) da fila para o Anki")
            self.flush_btn.setVisible(True)
        else:
            self.flush_btn.setVisible(False)

    def _on_flush_pending(self):
        """Reenvia a fila de fallback ao Anki e informa o resultado."""
        self.flush_btn.setEnabled(False)
        try:
            r = self.service.flush_fallback_to_anki()
        except ConnectionError:
            QMessageBox.warning(self, "Anki", "AnkiConnect indisponível. Tente novamente com o Anki aberto.")
            self.flush_btn.setEnabled(True)
            return
        except Exception as e:
            QMessageBox.critical(self, "Anki", f"Falha ao reenviar a fila: {e}")
            self.flush_btn.setEnabled(True)
            return

        msg = (f"Enviados: {r['sent']}\nJá existentes (duplicados): {r['duplicates']}\n"
               f"Descartados (vazios): {r['dropped']}\nAinda na fila: {r['kept']}")
        QMessageBox.information(self, "Fila reenviada", msg)
        self.flush_btn.setEnabled(True)
        self._refresh_pending_button()

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
