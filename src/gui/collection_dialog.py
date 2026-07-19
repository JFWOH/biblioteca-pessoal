"""Diálogo de gerenciamento de coleções."""

from PyQt6.QtWidgets import (
    QDialog, QVBoxLayout, QHBoxLayout, QLabel, QPushButton,
    QLineEdit, QListWidget, QListWidgetItem, QMessageBox,
    QFrame,
)
from PyQt6.QtCore import Qt, QSize, pyqtSignal
from PyQt6.QtGui import QFont

from src.core.database import LibraryDB
from src.gui.styles import emoji_icon


class CollectionDialog(QDialog):
    """Diálogo para criar, editar e gerenciar coleções."""

    collections_changed = pyqtSignal()

    def __init__(self, db: LibraryDB, parent=None):
        super().__init__(parent)
        self._db = db
        self.setWindowTitle("📂 Gerenciar Coleções")
        self.setMinimumSize(QSize(500, 450))
        self.setModal(True)
        self._setup_ui()
        self._load_collections()

    def _setup_ui(self):
        layout = QVBoxLayout(self)
        layout.setContentsMargins(20, 20, 20, 20)
        layout.setSpacing(16)

        # Título
        title = QLabel("📂 Coleções")
        font = title.font()
        font.setPointSize(16)
        font.setWeight(QFont.Weight.Bold)
        title.setFont(font)
        title.setObjectName("collectionDialogTitle")
        layout.addWidget(title)

        subtitle = QLabel(
            "Organize seus livros em coleções temáticas. "
            "Cada livro pode pertencer a múltiplas coleções."
        )
        subtitle.setWordWrap(True)
        subtitle.setObjectName("collectionDialogSubtitle")
        layout.addWidget(subtitle)

        # Criar nova coleção
        create_frame = QFrame()
        create_frame.setObjectName("collectionCreateFrame")
        create_layout = QHBoxLayout(create_frame)
        create_layout.setContentsMargins(12, 8, 12, 8)

        self._new_name = QLineEdit()
        self._new_name.setPlaceholderText("Nome da nova coleção...")
        self._new_name.setObjectName("collectionNewNameInput")
        self._new_name.returnPressed.connect(self._create_collection)
        create_layout.addWidget(self._new_name, stretch=1)

        create_btn = QPushButton("+ Criar")
        create_btn.setObjectName("collectionCreateBtn")
        create_btn.clicked.connect(self._create_collection)
        create_layout.addWidget(create_btn)

        layout.addWidget(create_frame)

        # Lista de coleções existentes
        self._collection_list = QListWidget()
        self._collection_list.setObjectName("collectionList")
        layout.addWidget(self._collection_list, stretch=1)

        # Botões de ação
        actions = QHBoxLayout()

        self._rename_btn = QPushButton("Renomear")
        self._rename_btn.setIcon(emoji_icon("✏️"))
        self._rename_btn.setObjectName("secondaryBtn")
        self._rename_btn.clicked.connect(self._rename_collection)
        actions.addWidget(self._rename_btn)

        self._delete_btn = QPushButton("Excluir")
        self._delete_btn.setIcon(emoji_icon("🗑"))
        self._delete_btn.setObjectName("dangerBtnSmall")
        self._delete_btn.clicked.connect(self._delete_collection)
        actions.addWidget(self._delete_btn)

        actions.addStretch()

        close_btn = QPushButton("Fechar")
        close_btn.setObjectName("secondaryBtn")
        close_btn.clicked.connect(self.accept)
        actions.addWidget(close_btn)

        layout.addLayout(actions)

    def _load_collections(self):
        """Carrega coleções do banco."""
        self._collection_list.clear()
        collections = self._db.get_all_collections()
        for col in collections:
            book_count = len(self._db.get_books_in_collection(col["id"]))
            item = QListWidgetItem(f"📁 {col['name']}  ({book_count} livros)")
            item.setData(Qt.ItemDataRole.UserRole, col["id"])
            item.setData(Qt.ItemDataRole.UserRole + 1, col["name"])
            self._collection_list.addItem(item)

        if not collections:
            empty = QListWidgetItem("Nenhuma coleção criada ainda")
            empty.setFlags(Qt.ItemFlag.NoItemFlags)
            self._collection_list.addItem(empty)

    def _create_collection(self):
        name = self._new_name.text().strip()
        if not name:
            return

        try:
            self._db.create_collection(name)
            self._new_name.clear()
            self._load_collections()
            self.collections_changed.emit()
        except Exception as e:
            QMessageBox.warning(self, "Erro", f"Erro ao criar coleção: {e}")

    def _rename_collection(self):
        item = self._collection_list.currentItem()
        if not item or not item.data(Qt.ItemDataRole.UserRole):
            return

        col_id = item.data(Qt.ItemDataRole.UserRole)
        old_name = item.data(Qt.ItemDataRole.UserRole + 1)

        from PyQt6.QtWidgets import QInputDialog
        new_name, ok = QInputDialog.getText(
            self, "Renomear Coleção", "Novo nome:", text=old_name
        )
        if ok and new_name.strip():
            self._db.rename_collection(col_id, new_name.strip())
            self._load_collections()
            self.collections_changed.emit()

    def _delete_collection(self):
        item = self._collection_list.currentItem()
        if not item or not item.data(Qt.ItemDataRole.UserRole):
            return

        col_id = item.data(Qt.ItemDataRole.UserRole)
        name = item.data(Qt.ItemDataRole.UserRole + 1)

        reply = QMessageBox.question(
            self, "Excluir Coleção",
            f'Excluir a coleção "{name}"?\n'
            "(Os livros não serão removidos da biblioteca)",
        )
        if reply == QMessageBox.StandardButton.Yes:
            self._db.delete_collection(col_id)
            self._load_collections()
            self.collections_changed.emit()


class AddToCollectionDialog(QDialog):
    """Diálogo para adicionar um livro a coleções."""

    def __init__(self, db: LibraryDB, book_id: int, parent=None):
        super().__init__(parent)
        self._db = db
        self._book_id = book_id
        self.setWindowTitle("Adicionar a Coleção")
        self.setMinimumSize(QSize(350, 300))
        self.setModal(True)
        self._setup_ui()

    def _setup_ui(self):
        layout = QVBoxLayout(self)
        layout.setContentsMargins(16, 16, 16, 16)
        layout.setSpacing(12)

        title = QLabel("📂 Adicionar a Coleção")
        font = title.font()
        font.setPointSize(13)
        font.setWeight(QFont.Weight.Bold)
        title.setFont(font)
        title.setObjectName("collectionDialogTitle")
        layout.addWidget(title)

        # Lista de coleções com checkboxes
        self._collection_list = QListWidget()
        self._collection_list.setObjectName("addToCollectionList")

        collections = self._db.get_all_collections()
        book_collections = {
            c["id"] for c in self._db.get_book_collections(self._book_id)
        }

        for col in collections:
            item = QListWidgetItem(f"📁 {col['name']}")
            item.setData(Qt.ItemDataRole.UserRole, col["id"])
            item.setFlags(item.flags() | Qt.ItemFlag.ItemIsUserCheckable)
            item.setCheckState(
                Qt.CheckState.Checked if col["id"] in book_collections
                else Qt.CheckState.Unchecked
            )
            self._collection_list.addItem(item)
        layout.addWidget(self._collection_list, stretch=1)

        # Botões
        btn_layout = QHBoxLayout()
        btn_layout.addStretch()

        cancel_btn = QPushButton("Cancelar")
        cancel_btn.setObjectName("secondaryBtn")
        cancel_btn.clicked.connect(self.reject)
        btn_layout.addWidget(cancel_btn)

        save_btn = QPushButton("Salvar")
        save_btn.setIcon(emoji_icon("💾"))
        save_btn.setObjectName("primaryBtn")
        save_btn.clicked.connect(self._save)
        btn_layout.addWidget(save_btn)

        layout.addLayout(btn_layout)

    def _save(self):
        """Salva as associações livro-coleção."""
        for i in range(self._collection_list.count()):
            item = self._collection_list.item(i)
            col_id = item.data(Qt.ItemDataRole.UserRole)
            if item.checkState() == Qt.CheckState.Checked:
                self._db.add_book_to_collection(self._book_id, col_id)
            else:
                self._db.remove_book_from_collection(self._book_id, col_id)
        self.accept()
