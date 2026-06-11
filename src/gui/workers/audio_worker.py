import logging
from PyQt6.QtCore import QThread, pyqtSignal
from src.core.tts.tts_router import TTSRouter
from src.core.tts.voice_profile import NarrationRole
from src.core.tts.text_preprocessor import TTSTextPreprocessor
from src.core.audio.tts_backend import TTSBackendUnavailable

logger = logging.getLogger(__name__)


class AudioWorker(QThread):
    """Worker assíncrono para reprodução de áudio na thread de background.

    Phase 13: Now uses the unified TTSRouter instead of direct pyttsx3.
    Supports distinct narration roles (book narrator vs assistant).
    Garante que a interface gráfica permaneça 100% responsiva.
    """

    playback_started = pyqtSignal()
    playback_finished = pyqtSignal(int)  # quantidade de chunks falados
    error_occurred = pyqtSignal(str)
    provider_changed = pyqtSignal(str)  # emitted when fallback occurs

    def __init__(self, text: str, rate: float = 1.0, volume: float = 1.0,
                 role: NarrationRole = NarrationRole.BOOK_NARRATOR,
                 router: TTSRouter | None = None,
                 parent=None):
        super().__init__(parent)
        self._text = text
        self._rate = rate
        self._volume = volume
        self._role = role
        self._router = router
        self._is_cancelled = False
        
        # Load configuration profiles from MainWindow IN THE MAIN THREAD
        self._book_profile_data = None
        self._assistant_profile_data = None
        if parent is not None and hasattr(parent, "window"):
            parent_window = parent.window()
            config = getattr(parent_window, "_config", None)
            if config:
                tts_cfg = config.tts_config
                self._book_profile_data = tts_cfg.get("book_narrator", {})
                self._assistant_profile_data = tts_cfg.get("assistant", {})

    def run(self) -> None:
        """Execução paralela na thread de background."""
        try:
            # Initialize router if not provided
            if self._router is None:
                logger.info("AUDIO_WORKER: ROUTER_REUSED=false (creating new router)")
                self._router = TTSRouter(TTSTextPreprocessor())
                self._router.auto_register_providers()
                self._router.initialize()
            else:
                logger.info("AUDIO_WORKER: ROUTER_REUSED=true (reusing persistent router)")

            # Apply loaded profiles
            if self._book_profile_data is not None and self._assistant_profile_data is not None:
                from src.core.tts.voice_profile import VoiceProfile
                self._router.set_book_profile(VoiceProfile.from_dict(self._book_profile_data))
                self._router.set_assistant_profile(VoiceProfile.from_dict(self._assistant_profile_data))
                logger.info("AUDIO_WORKER: Loaded voice profiles from config")

            # Apply rate/volume overrides to the appropriate profile
            if self._role == NarrationRole.BOOK_NARRATOR:
                profile = self._router.get_book_profile()
            else:
                profile = self._router.get_assistant_profile()

            if self._rate != 1.0:
                profile.rate = self._rate
            if self._volume != 1.0:
                profile.volume = self._volume

            self.playback_started.emit()

            # Report active provider
            active = self._router.get_active_provider_name()
            if active != "none":
                self.provider_changed.emit(active)

            # Synthesize and play through the router
            chunks_spoken = self._router.speak(
                self._text,
                role=self._role,
                preprocess=True,
            )

            # Report final provider used
            final_provider = self._router.get_active_provider_name()
            if final_provider != "none":
                self.provider_changed.emit(final_provider)

            self.playback_finished.emit(chunks_spoken)

        except TTSBackendUnavailable as e:
            logger.error("AUDIO_WORKER: Backend indisponivel: %s", e)
            self.error_occurred.emit(str(e))
        except Exception as e:
            logger.error("AUDIO_WORKER: Erro inesperado: %s", e)
            self.error_occurred.emit(f"Erro ao reproduzir audio: {e}")

    def stop(self) -> None:
        """Interrompe a leitura de forma best-effort e graciosa."""
        self._is_cancelled = True
        if self._router:
            self._router.stop()
        self.requestInterruption()
