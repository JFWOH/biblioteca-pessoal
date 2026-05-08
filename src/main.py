"""Entry point da aplicação Biblioteca Pessoal."""

import sys
from pathlib import Path

# Garante que o diretório raiz do projeto está no sys.path
project_root = str(Path(__file__).resolve().parent.parent)
if project_root not in sys.path:
    sys.path.insert(0, project_root)


def main():
    """Inicia a aplicação."""
    from PyQt6.QtWidgets import QApplication
    from PyQt6.QtCore import Qt
    from PyQt6.QtGui import QFont

    # WebEngine exige que isso seja definido ANTES do QApplication
    QApplication.setAttribute(Qt.ApplicationAttribute.AA_ShareOpenGLContexts)
    # Importa WebEngine antes do QApplication para evitar erro de inicialização
    from PyQt6.QtWebEngineWidgets import QWebEngineView  # noqa: F401

    app = QApplication(sys.argv)
    app.setApplicationName("Biblioteca Pessoal")
    app.setApplicationVersion("0.1.0")
    app.setOrganizationName("BibliotecaPessoal")

    # Fonte padrão
    font = QFont("Segoe UI", 10)
    app.setFont(font)

    from src.gui.main_window import MainWindow
    window = MainWindow()
    window.show()

    sys.exit(app.exec())


if __name__ == "__main__":
    main()
