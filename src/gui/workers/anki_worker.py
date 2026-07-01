import logging
from PyQt6.QtCore import QThread, pyqtSignal
from src.core.anki_service import AnkiService

logger = logging.getLogger(__name__)

class AnkiAddNoteWorker(QThread):
    """
    Worker assíncrono para adicionar uma nota no Anki via AnkiService.
    Evita bloqueio da UI durante o request HTTP.
    """
    finished = pyqtSignal(object)  # Retorna o ID da nota ou None se foi pro fallback
    error = pyqtSignal(str)

    def __init__(self, service: AnkiService, deck_name: str, front: str, back: str, tags: list = None):
        super().__init__()
        self.service = service
        self.deck_name = deck_name
        self.front = front
        self.back = back
        self.tags = tags or []

    def run(self):
        try:
            note_id = self.service.add_basic_note(
                deck_name=self.deck_name,
                front=self.front,
                back=self.back,
                tags=self.tags
            )
            self.finished.emit(note_id)
        except Exception as exc:
            logger.error(f"Erro no AnkiAddNoteWorker: {exc}")
            self.error.emit(str(exc))
