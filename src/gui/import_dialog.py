"""Diálogo de importação de documentos."""

from pathlib import Path

from PyQt6.QtWidgets import (
    QDialog, QVBoxLayout, QHBoxLayout, QLabel, QPushButton,
    QFileDialog, QProgressBar, QTextEdit, QCheckBox, QGroupBox,
    QListWidget, QListWidgetItem,
)
from PyQt6.QtCore import QThread, pyqtSignal, QSize
from PyQt6.QtGui import QFont

from src.utils.constants import FILE_FILTER
from src.utils.file_utils import format_file_size, get_file_extension


class ImportWorker(QThread):
    """Worker thread para importação em background."""

    progress = pyqtSignal(int, int, str)   # current, total, filename
    file_imported = pyqtSignal(dict)        # book data
    file_skipped = pyqtSignal(str, str)     # filepath, reason
    finished = pyqtSignal(int, int)         # imported, skipped

    def __init__(self, library_manager, files: list[str]):
        super().__init__()
        self._library = library_manager
        self._files = files

    def run(self):
        imported = 0
        skipped = 0
        total = len(self._files)

        for i, filepath in enumerate(self._files):
            name = Path(filepath).name
            self.progress.emit(i + 1, total, name)

            try:
                book, is_new = self._library.import_file(filepath)
                if book and is_new:
                    imported += 1
                    self.file_imported.emit(book)
                else:
                    skipped += 1
                    self.file_skipped.emit(filepath, "Já existe na biblioteca (duplicata)")
            except Exception as e:
                skipped += 1
                self.file_skipped.emit(filepath, str(e))

        self.finished.emit(imported, skipped)


class ImportDialog(QDialog):
    """Diálogo rico para importação de documentos."""

    import_completed = pyqtSignal()

    def __init__(self, library_manager, parent=None, initial_files: list[str] | None = None):
        super().__init__(parent)
        self._library = library_manager
        self._files: list[str] = []
        self._worker: ImportWorker | None = None
        self.setWindowTitle("Importar Documentos")
        self.setMinimumSize(QSize(600, 500))
        self.setModal(True)
        self._setup_ui()
        # Pré-carrega arquivos (ex.: vindos do arraste-e-solte na janela).
        if initial_files:
            self.add_files(initial_files)

    def _setup_ui(self):
        layout = QVBoxLayout(self)
        layout.setContentsMargins(20, 20, 20, 20)
        layout.setSpacing(16)

        # Título
        title = QLabel("📂 Importar Documentos")
        font = title.font()
        font.setPointSize(16)
        font.setWeight(QFont.Weight.Bold)
        title.setFont(font)
        title.setObjectName("importDialogTitle")
        layout.addWidget(title)

        subtitle = QLabel(
            "Selecione arquivos ou uma pasta para importar à biblioteca. "
            "Metadados e capas serão extraídos automaticamente."
        )
        subtitle.setWordWrap(True)
        subtitle.setObjectName("importDialogSubtitle")
        layout.addWidget(subtitle)

        # Botões de seleção
        select_layout = QHBoxLayout()

        files_btn = QPushButton("📄  Selecionar Arquivos")
        files_btn.setObjectName("primaryBtn")
        files_btn.clicked.connect(self._select_files)
        select_layout.addWidget(files_btn)

        folder_btn = QPushButton("📁  Selecionar Pasta")
        folder_btn.setObjectName("secondaryBtn")
        folder_btn.clicked.connect(self._select_folder)
        select_layout.addWidget(folder_btn)

        select_layout.addStretch()
        layout.addLayout(select_layout)

        # Lista de arquivos selecionados
        files_group = QGroupBox("Arquivos selecionados")
        files_group.setObjectName("importFilesGroup")
        files_layout = QVBoxLayout(files_group)

        self._file_list = QListWidget()
        self._file_list.setObjectName("importFileList")
        self._file_list.setMinimumHeight(120)
        files_layout.addWidget(self._file_list)

        self._files_count = QLabel("Nenhum arquivo selecionado")
        self._files_count.setObjectName("importFilesCount")
        files_layout.addWidget(self._files_count)

        layout.addWidget(files_group)

        # Opções
        options_layout = QHBoxLayout()

        self._detect_dups = QCheckBox("Detectar duplicatas")
        self._detect_dups.setChecked(True)
        self._detect_dups.setObjectName("importOptionCheckbox")
        options_layout.addWidget(self._detect_dups)

        self._extract_meta = QCheckBox("Extrair metadados automaticamente")
        self._extract_meta.setChecked(True)
        self._extract_meta.setObjectName("importOptionCheckbox")
        options_layout.addWidget(self._extract_meta)

        options_layout.addStretch()
        layout.addLayout(options_layout)

        # Progresso
        self._progress_bar = QProgressBar()
        self._progress_bar.setRange(0, 100)
        self._progress_bar.setValue(0)
        self._progress_bar.setFixedHeight(8)
        self._progress_bar.setTextVisible(False)
        self._progress_bar.hide()
        layout.addWidget(self._progress_bar)

        self._progress_label = QLabel()
        self._progress_label.setObjectName("importProgressLabel")
        self._progress_label.hide()
        layout.addWidget(self._progress_label)

        # Log de importação
        self._log = QTextEdit()
        self._log.setReadOnly(True)
        self._log.setFixedHeight(80)
        self._log.setObjectName("importLog")
        self._log.hide()
        layout.addWidget(self._log)

        # Botões de ação
        btn_layout = QHBoxLayout()
        btn_layout.addStretch()

        self._cancel_btn = QPushButton("Cancelar")
        self._cancel_btn.setObjectName("secondaryBtn")
        self._cancel_btn.clicked.connect(self.reject)
        btn_layout.addWidget(self._cancel_btn)

        self._import_btn = QPushButton("🚀  Importar")
        self._import_btn.setObjectName("primaryBtn")
        self._import_btn.setEnabled(False)
        self._import_btn.clicked.connect(self._start_import)
        btn_layout.addWidget(self._import_btn)

        layout.addLayout(btn_layout)

    def add_files(self, files: list[str]):
        """Define a lista de arquivos a importar e atualiza a UI.

        API pública usada pelo arraste-e-solte do MainWindow (que já filtrou
        os formatos suportados) e pelo parâmetro ``initial_files``. Substitui
        a seleção atual — mesmo comportamento de "Selecionar Arquivos".
        """
        self._files = list(files)
        self._update_file_list()

    def _select_files(self):
        files, _ = QFileDialog.getOpenFileNames(self, "Selecionar Arquivos", "", FILE_FILTER)
        if files:
            self._files = files
            self._update_file_list()

    def _select_folder(self):
        folder = QFileDialog.getExistingDirectory(self, "Selecionar Pasta")
        if folder:
            from src.utils.file_utils import find_documents
            docs = find_documents(folder)
            self._files = [str(d) for d in docs]
            self._update_file_list()

    def _update_file_list(self):
        self._file_list.clear()
        total_size = 0
        for f in self._files:
            p = Path(f)
            size = p.stat().st_size if p.exists() else 0
            total_size += size
            ext = get_file_extension(f).upper()
            item = QListWidgetItem(f"[{ext}] {p.name}  ({format_file_size(size)})")
            self._file_list.addItem(item)

        count = len(self._files)
        self._files_count.setText(
            f"{count} {'arquivo' if count == 1 else 'arquivos'} "
            f"({format_file_size(total_size)})"
        )
        self._import_btn.setEnabled(count > 0)

    def _start_import(self):
        if not self._files:
            return

        self._import_btn.setEnabled(False)
        self._progress_bar.show()
        self._progress_label.show()
        self._log.show()
        self._log.clear()

        self._worker = ImportWorker(self._library, self._files)
        self._worker.progress.connect(self._on_progress)
        self._worker.file_imported.connect(self._on_imported)
        self._worker.file_skipped.connect(self._on_skipped)
        self._worker.finished.connect(self._on_finished)
        self._worker.start()

    def _on_progress(self, current: int, total: int, filename: str):
        pct = int(current / total * 100)
        self._progress_bar.setValue(pct)
        self._progress_label.setText(f"Importando {current}/{total}: {filename}")

    def _on_imported(self, book: dict):
        title = book.get("title", "?")
        self._log.append(f'✅ {title}')

    def _on_skipped(self, filepath: str, reason: str):
        name = Path(filepath).name
        self._log.append(f'⏭️ {name} — {reason}')

    def _on_finished(self, imported: int, skipped: int):
        self._progress_bar.setValue(100)
        self._progress_label.setText(
            f"✅ Concluído: {imported} importados, {skipped} ignorados"
        )
        self._import_btn.setText("Fechar")
        self._import_btn.setEnabled(True)
        self._import_btn.clicked.disconnect()
        self._import_btn.clicked.connect(self.accept)
        self.import_completed.emit()
