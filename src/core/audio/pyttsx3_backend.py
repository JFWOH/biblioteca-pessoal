import logging
from src.core.audio.tts_backend import TTSBackend, AudioReaderError, TTSBackendUnavailable

logger = logging.getLogger(__name__)

class Pyttsx3Backend(TTSBackend):
    """Implementação do backend de TTS usando a biblioteca offline pyttsx3."""

    def __init__(self):
        # Cache de configurações para serem aplicadas a cada nova engine recriada por chunk
        self._rate = 200
        self._volume = 1.0
        self._voice_id = None
        self._active_engine = None

        # Teste de importação defensiva no construtor
        try:
            import pyttsx3  # noqa: F401
        except ImportError as e:
            logger.warning("AUDIO: Biblioteca pyttsx3 nao instalada.")
            raise TTSBackendUnavailable(
                "Biblioteca pyttsx3 nao instalada. Por favor, instale usando: pip install pyttsx3"
            ) from e

    def speak(self, text: str) -> None:
        if not text:
            return
        
        try:
            import pyttsx3
            # Recria a engine por bloco para evitar travamento do event loop no SAPI5 no Windows
            engine = pyttsx3.init()
            
            # Re-aplica as propriedades cacheadas
            if self._rate is not None:
                engine.setProperty('rate', self._rate)
            if self._volume is not None:
                engine.setProperty('volume', self._volume)
            if self._voice_id is not None:
                engine.setProperty('voice', self._voice_id)
                
            self._active_engine = engine  # Torna a engine ativa para permitir stop() concorrente
            
            logger.info("AUDIO: speaking text block of size %d", len(text))
            
            # WORKAROUND: Se o stop() foi chamado de outra thread, o pyttsx3 pode não limpar a flag _inLoop
            if hasattr(engine, '_inLoop'):
                engine._inLoop = False
                
            engine.say(text)
            engine.runAndWait()
        except Exception as e:
            logger.error("AUDIO: Erro durante execucao do speak: %s", e)
            raise AudioReaderError(f"Erro no speak do pyttsx3: {e}") from e
        finally:
            self._active_engine = None

    def stop(self) -> None:
        logger.info("AUDIO: stop requested")
        if self._active_engine:
            try:
                self._active_engine.stop()
                logger.info("AUDIO: active engine stopped")
            except Exception as e:
                # Silencia o erro, mantendo semântica best-effort
                logger.warning("AUDIO: Falha ao tentar parar active engine: %s", e)

    def pause(self) -> None:
        # pyttsx3 nativamente não tem suporte robusto cross-platform para pause
        logger.info("AUDIO: pause requested (no-op on pyttsx3)")

    def resume(self) -> None:
        # pyttsx3 nativamente não tem suporte robusto cross-platform para resume
        logger.info("AUDIO: resume requested (no-op on pyttsx3)")

    def set_rate(self, rate: int) -> None:
        logger.info("AUDIO: caching rate %d", rate)
        self._rate = rate
        if self._active_engine:
            try:
                self._active_engine.setProperty('rate', rate)
            except Exception as e:
                logger.warning("AUDIO: Falha ao ajustar rate na engine ativa: %s", e)

    def set_volume(self, volume: float) -> None:
        volume_val = max(0.0, min(1.0, volume))
        logger.info("AUDIO: caching volume %.2f", volume_val)
        self._volume = volume_val
        if self._active_engine:
            try:
                self._active_engine.setProperty('volume', volume_val)
            except Exception as e:
                logger.warning("AUDIO: Falha ao ajustar volume na engine ativa: %s", e)

    def list_voices(self) -> list:
        try:
            import pyttsx3
            temp_engine = pyttsx3.init()
            voices = temp_engine.getProperty('voices')
            voice_list = []
            for v in voices:
                voice_list.append({
                    "id": getattr(v, "id", ""),
                    "name": getattr(v, "name", ""),
                    "languages": getattr(v, "languages", []),
                })
            return voice_list
        except Exception as e:
            logger.warning("AUDIO: Falha ao listar vozes: %s", e)
            return []

    def set_voice(self, voice_id: str) -> None:
        logger.info("AUDIO: caching voice %s", voice_id)
        self._voice_id = voice_id
        if self._active_engine:
            try:
                self._active_engine.setProperty('voice', voice_id)
            except Exception as e:
                logger.warning("AUDIO: Falha ao definir voz na engine ativa: %s", e)
