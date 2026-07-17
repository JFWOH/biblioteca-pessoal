"""Sobreposição visual de arraste-e-solte para importação de arquivos."""

from pathlib import Path

from PyQt6.QtWidgets import QWidget, QVBoxLayout, QLabel
from PyQt6.QtCore import Qt

from src.utils.constants import SUPPORTED_EXTENSIONS


def supported_files_from_urls(urls) -> list[str]:
    """Filtra uma lista de ``QUrl``, devolvendo só caminhos locais suportados.

    Descarta URLs não-locais (http, etc.) e arquivos cuja extensão não está
    em ``SUPPORTED_EXTENSIONS``. Preserva a ordem original. Função pura (sem
    Qt widgets) para ser testável sem instanciar a janela principal.
    """
    files: list[str] = []
    for url in urls:
        path = url.toLocalFile()
        if path and Path(path).suffix.lower().lstrip(".") in SUPPORTED_EXTENSIONS:
            files.append(path)
    return files


class DropOverlay(QWidget):
    """Camada semi-transparente exibida enquanto o usuário arrasta arquivos.

    Cobre a janela inteira com o convite "Solte para importar". É apenas
    decoração: não intercepta os eventos de arraste (``WA_TransparentForMouseEvents``),
    que continuam chegando à ``MainWindow`` (que trata o ``dropEvent``). Todas
    as cores vêm do QSS por objectName (``dropOverlay`` / ``dropOverlayLabel`` /
    ``dropOverlayIcon``) nos 3 temas — nenhuma cor hardcoded aqui (padrão Onda 0).
    """

    def __init__(self, parent=None):
        super().__init__(parent)
        self.setObjectName("dropOverlay")
        # Necessário para que o background definido via QSS seja pintado.
        self.setAttribute(Qt.WidgetAttribute.WA_StyledBackground, True)
        # A sobreposição não deve "roubar" eventos de mouse/arraste do pai.
        self.setAttribute(Qt.WidgetAttribute.WA_TransparentForMouseEvents, True)

        layout = QVBoxLayout(self)
        layout.setAlignment(Qt.AlignmentFlag.AlignCenter)
        layout.setSpacing(12)

        self._icon = QLabel("📥")
        self._icon.setObjectName("dropOverlayIcon")
        self._icon.setAlignment(Qt.AlignmentFlag.AlignCenter)
        layout.addWidget(self._icon)

        self._label = QLabel("Solte para importar")
        self._label.setObjectName("dropOverlayLabel")
        self._label.setAlignment(Qt.AlignmentFlag.AlignCenter)
        layout.addWidget(self._label)

        self.hide()

    def cover(self, rect) -> None:
        """Posiciona a sobreposição sobre ``rect`` (área do widget-pai) e mostra."""
        self.setGeometry(rect)
        self.raise_()
        self.show()
