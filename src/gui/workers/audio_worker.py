import logging
from PyQt6.QtCore import QThread, pyqtSignal
from src.core.audio.tts_backend import TTSBackendUnavailable
from src.core.audio.pyttsx3_backend import Pyttsx3Backend
from src.core.audio.audio_reader_service import AudioReaderService

logger = logging.getLogger(__name__)

class AudioWorker(QThread):
    """Worker assíncrono para reprodução de áudio na thread de background.
    
    Garante que a interface gráfica permaneça 100% responsiva.
    """

    playback_started = pyqtSignal()
    playback_finished = pyqtSignal(int)  # quantidade de chunks falados
    error_occurred = pyqtSignal(str)

    def __init__(self, text: str, rate: int = 180, volume: float = 1.0, parent=None):
        super().__init__(parent)
        self._text = text
        self._rate = rate
        self._volume = volume
        self._service = None

    def run(self) -> None:
        """Execução paralela na thread de background."""
        try:
            # Inicializa o backend local de forma lazy/defensiva
            backend = Pyttsx3Backend()
            self._service = AudioReaderService(backend)
            
            # Aplica configurações iniciais
            self._service.set_rate(self._rate)
            self._service.set_volume(self._volume)

            self.playback_started.emit()
            
            # Inicia reprodução
            chunks_spoken = self._service.read_text(self._text)
            self.playback_finished.emit(chunks_spoken)

        except TTSBackendUnavailable as e:
            logger.error("AUDIO_WORKER: Backend indisponivel: %s", e)
            self.error_occurred.emit(str(e))
        except Exception as e:
            logger.error("AUDIO_WORKER: Erro inesperado: %s", e)
            self.error_occurred.emit(f"Erro ao reproduzir audio: {e}")

    def stop(self) -> None:
        """Interrompe a leitura de forma best-effort e graciosa."""
        if self._service:
            self._service.stop()
        self.requestInterruption()
