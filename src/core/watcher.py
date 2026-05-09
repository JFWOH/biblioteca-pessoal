"""Monitoramento de diretórios para auto-importação de documentos."""

import time
from pathlib import Path
from typing import Callable

from PyQt6.QtCore import QThread, pyqtSignal, QTimer

from src.utils.file_utils import is_supported_format, find_documents
from src.core.library import LibraryManager


class DirectoryWatcher(QThread):
    """Thread que monitora diretórios para novos arquivos."""

    file_found = pyqtSignal(str)          # caminho do arquivo novo
    import_completed = pyqtSignal(int)     # número de arquivos importados
    error_occurred = pyqtSignal(str)       # mensagem de erro

    def __init__(self, library: LibraryManager, watch_dirs: list[str],
                 interval_seconds: int = 30, parent=None):
        super().__init__(parent)
        self._library = library
        self._watch_dirs = [Path(d) for d in watch_dirs]
        self._interval = interval_seconds
        self._running = False
        self._known_files: set[str] = set()

    def run(self):
        """Loop principal de monitoramento."""
        self._running = True

        # Popula arquivos já conhecidos no primeiro scan
        self._known_files = self._scan_existing()

        while self._running:
            try:
                current_files = self._scan_existing()
                new_files = current_files - self._known_files

                if new_files:
                    count = 0
                    for filepath in sorted(new_files):
                        try:
                            self.file_found.emit(filepath)
                            book, is_new = self._library.import_file(filepath)
                            if book and is_new:
                                count += 1
                        except Exception as e:
                            self.error_occurred.emit(
                                f"Erro ao importar {Path(filepath).name}: {e}"
                            )
                    if count > 0:
                        self.import_completed.emit(count)

                self._known_files = current_files

            except Exception as e:
                self.error_occurred.emit(f"Erro no monitoramento: {e}")

            # Espera com checagem periódica para permitir parada rápida
            for _ in range(self._interval * 2):
                if not self._running:
                    break
                time.sleep(0.5)

    def _scan_existing(self) -> set[str]:
        """Varre todos os diretórios monitorados."""
        files = set()
        for watch_dir in self._watch_dirs:
            if watch_dir.exists():
                for doc in find_documents(str(watch_dir), recursive=True):
                    files.add(str(doc))
        return files

    def stop(self):
        """Para o monitoramento."""
        self._running = False

    def add_directory(self, path: str):
        """Adiciona um diretório para monitorar."""
        p = Path(path)
        if p.exists() and p not in self._watch_dirs:
            self._watch_dirs.append(p)
            # Re-scan para não importar existentes como novos
            new_files = set()
            for doc in find_documents(str(p), recursive=True):
                new_files.add(str(doc))
            self._known_files |= new_files

    def remove_directory(self, path: str):
        """Remove um diretório do monitoramento."""
        p = Path(path)
        if p in self._watch_dirs:
            self._watch_dirs.remove(p)

    @property
    def watching(self) -> list[str]:
        """Lista de diretórios sendo monitorados."""
        return [str(d) for d in self._watch_dirs]

    @property
    def is_active(self) -> bool:
        return self._running and self.isRunning()
