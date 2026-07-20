"""Entry point da aplicação Biblioteca Pessoal."""

import sys
import os
from pathlib import Path

# Garante que o diretório raiz do projeto está no sys.path
project_root = str(Path(__file__).resolve().parent.parent)
if project_root not in sys.path:
    sys.path.insert(0, project_root)

# Force HuggingFace offline mode unconditionally at process startup to prevent network hangs
os.environ["HF_HUB_OFFLINE"] = "1"




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

    # Splash imediato (rodada E1): feedback visual antes de construir a
    # MainWindow — em disco frio os imports da GUI ainda custam segundos e,
    # sem isso, o duplo-clique parece "não ter funcionado".
    from PyQt6.QtWidgets import QSplashScreen
    from PyQt6.QtGui import QColor, QPainter, QPixmap
    from PyQt6.QtCore import QRect
    pixmap = QPixmap(420, 220)
    pixmap.fill(QColor("#1e2227"))
    painter = QPainter(pixmap)
    title_font = QFont("Segoe UI", 16)
    title_font.setBold(True)
    painter.setFont(title_font)
    painter.setPen(QColor("#e4e4e7"))
    painter.drawText(QRect(0, 78, 420, 40),
                     Qt.AlignmentFlag.AlignCenter, "📚 Biblioteca Pessoal")
    painter.setFont(QFont("Segoe UI", 10))
    painter.setPen(QColor("#a1a1aa"))
    painter.drawText(QRect(0, 122, 420, 30),
                     Qt.AlignmentFlag.AlignCenter, "Iniciando…")
    painter.end()
    splash = QSplashScreen(pixmap)
    splash.show()
    app.processEvents()  # pinta o splash antes do trabalho pesado

    from src.gui.main_window import MainWindow
    window = MainWindow()
    window.show()
    splash.finish(window)

    sys.exit(app.exec())


if __name__ == "__main__":
    main()
