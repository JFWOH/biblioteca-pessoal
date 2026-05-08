"""Widget de gerenciamento de tags para livros."""

from PyQt6.QtWidgets import (
    QWidget, QHBoxLayout, QVBoxLayout, QLabel, QPushButton,
    QFrame, QDialog, QLineEdit, QMessageBox,
    QListWidget, QListWidgetItem,
)
from PyQt6.QtCore import Qt, pyqtSignal, QSize
from PyQt6.QtGui import QFont

from src.core.database import LibraryDB

TAG_COLORS = [
    "#ef4444", "#f97316", "#fbbf24", "#34d399",
    "#3b82f6", "#6366f1", "#8b5cf6", "#ec4899",
]


class TagBadge(QFrame):
    """Badge visual de tag."""
    remove_requested = pyqtSignal(int)

    def __init__(self, tag: dict, removable=True, parent=None):
        super().__init__(parent)
        color = tag.get("color", "#6366f1")
        self.setStyleSheet(f"background:{color}22;border:1px solid {color}55;border-radius:12px;")
        lay = QHBoxLayout(self)
        lay.setContentsMargins(10, 4, 6 if removable else 10, 4)
        lay.setSpacing(4)
        dot = QLabel("●")
        dot.setStyleSheet(f"color:{color};font-size:8px;border:none;")
        lay.addWidget(dot)
        name = QLabel(tag.get("name", ""))
        name.setStyleSheet(f"color:{color};font-size:11px;font-weight:600;border:none;")
        lay.addWidget(name)
        if removable:
            x = QPushButton("✕")
            x.setFixedSize(16, 16)
            x.setStyleSheet(f"background:transparent;border:none;color:{color}88;font-size:10px;")
            x.clicked.connect(lambda: self.remove_requested.emit(tag.get("id", 0)))
            lay.addWidget(x)


class TagManager(QWidget):
    """Widget para exibir e gerenciar tags de um livro."""
    tags_changed = pyqtSignal(int)

    def __init__(self, db: LibraryDB, parent=None):
        super().__init__(parent)
        self._db = db
        self._book_id = 0
        layout = QVBoxLayout(self)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(8)
        header = QHBoxLayout()
        lbl = QLabel("🏷️ Tags")
        lbl.setStyleSheet("color:#a1a1aa;font-size:12px;font-weight:600;")
        header.addWidget(lbl)
        header.addStretch()
        add_btn = QPushButton("+ Tag")
        add_btn.setStyleSheet("background:rgba(99,102,241,0.15);border:none;border-radius:4px;padding:3px 10px;color:#818cf8;font-size:11px;font-weight:600;")
        add_btn.clicked.connect(self._show_add_dialog)
        header.addWidget(add_btn)
        layout.addLayout(header)
        self._tags_container = QWidget()
        self._tags_layout = QHBoxLayout(self._tags_container)
        self._tags_layout.setContentsMargins(0, 0, 0, 0)
        self._tags_layout.setSpacing(6)
        self._tags_layout.setAlignment(Qt.AlignmentFlag.AlignLeft)
        layout.addWidget(self._tags_container)

    def set_book(self, book_id: int):
        self._book_id = book_id
        self._load_tags()

    def _load_tags(self):
        while self._tags_layout.count():
            item = self._tags_layout.takeAt(0)
            if item.widget():
                item.widget().deleteLater()
        if not self._book_id:
            return
        tags = self._db.get_book_tags(self._book_id)
        for tag in tags:
            badge = TagBadge(tag)
            badge.remove_requested.connect(self._remove_tag)
            self._tags_layout.addWidget(badge)
        if not tags:
            e = QLabel("Nenhuma tag")
            e.setStyleSheet("color:#52525b;font-size:11px;")
            self._tags_layout.addWidget(e)

    def _remove_tag(self, tag_id: int):
        self._db.remove_tag_from_book(self._book_id, tag_id)
        self._load_tags()
        self.tags_changed.emit(self._book_id)

    def _show_add_dialog(self):
        dialog = AddTagDialog(self._db, self._book_id, self)
        if dialog.exec() == QDialog.DialogCode.Accepted:
            self._load_tags()
            self.tags_changed.emit(self._book_id)


class AddTagDialog(QDialog):
    """Diálogo para criar ou selecionar tags."""

    def __init__(self, db: LibraryDB, book_id: int, parent=None):
        super().__init__(parent)
        self._db = db
        self._book_id = book_id
        self._color = TAG_COLORS[4]
        self.setWindowTitle("Adicionar Tag")
        self.setMinimumSize(QSize(350, 300))
        self.setModal(True)
        self._setup_ui()

    def _setup_ui(self):
        layout = QVBoxLayout(self)
        layout.setContentsMargins(16, 16, 16, 16)
        layout.setSpacing(10)
        title = QLabel("🏷️ Adicionar Tag")
        f = title.font()
        f.setPointSize(13)
        f.setWeight(QFont.Weight.Bold)
        title.setFont(f)
        title.setStyleSheet("color:#e4e4e7;")
        layout.addWidget(title)
        layout.addWidget(QLabel("Tags existentes:"))
        self._list = QListWidget()
        self._list.setMaximumHeight(100)
        self._list.setStyleSheet("background:#0f0f17;border:1px solid #27272a;border-radius:6px;color:#e4e4e7;font-size:12px;")
        all_tags = self._db.get_all_tags()
        book_ids = {t["id"] for t in self._db.get_book_tags(self._book_id)}
        for tag in all_tags:
            if tag["id"] not in book_ids:
                item = QListWidgetItem(f"● {tag['name']}")
                item.setData(Qt.ItemDataRole.UserRole, tag["id"])
                self._list.addItem(item)
        self._list.itemDoubleClicked.connect(self._add_existing)
        layout.addWidget(self._list)
        layout.addWidget(QLabel("Criar nova:"))
        self._name = QLineEdit()
        self._name.setPlaceholderText("Nome da tag...")
        self._name.setStyleSheet("background:#0f0f17;border:1px solid #27272a;border-radius:6px;padding:6px 10px;color:#e4e4e7;font-size:12px;")
        layout.addWidget(self._name)
        colors = QHBoxLayout()
        colors.setSpacing(4)
        for c in TAG_COLORS:
            b = QPushButton()
            b.setFixedSize(22, 22)
            b.setStyleSheet(f"background:{c};border:2px solid transparent;border-radius:11px;")
            b.clicked.connect(lambda _, col=c: setattr(self, '_color', col))
            colors.addWidget(b)
        colors.addStretch()
        layout.addLayout(colors)
        btns = QHBoxLayout()
        btns.addStretch()
        cancel = QPushButton("Cancelar")
        cancel.setObjectName("secondaryBtn")
        cancel.clicked.connect(self.reject)
        btns.addWidget(cancel)
        create = QPushButton("✨ Criar")
        create.setObjectName("primaryBtn")
        create.clicked.connect(self._create)
        btns.addWidget(create)
        layout.addLayout(btns)

    def _add_existing(self, item):
        self._db.add_tag_to_book(self._book_id, item.data(Qt.ItemDataRole.UserRole))
        self.accept()

    def _create(self):
        name = self._name.text().strip()
        if not name:
            return
        tag_id = self._db.create_tag(name, self._color)
        self._db.add_tag_to_book(self._book_id, tag_id)
        self.accept()
