import logging
from src.core.audio.tts_backend import TTSBackend, AudioReaderError
from src.core.audio.text_chunker import split_text_for_tts, clean_text_for_tts

logger = logging.getLogger(__name__)

class AudioReaderService:
    """Serviço de alto nível que gerencia a reprodução e processamento de áudio."""

    def __init__(self, backend: TTSBackend, max_chunk_chars: int = 600):
        self.backend = backend
        self.max_chunk_chars = max_chunk_chars
        self._is_cancelled = False

    def reset(self) -> None:
        """Reseta o estado de cancelamento para permitir novas leituras."""
        self._is_cancelled = False

    def read_text(self, text: str) -> int:
        """Divide o texto em blocos e envia sequencialmente ao backend.
        
        Garante cancelamento ágil entre a leitura de blocos.
        Retorna a quantidade de blocos falados com sucesso.
        """
        if not text or not text.strip():
            return 0

        if self._is_cancelled:
            logger.info("AUDIO: read_text ignored because service is in cancelled state")
            return 0

        # Debug instrumentation
        raw_repr = repr(text[:300])
        cleaned_text = clean_text_for_tts(text)
        cleaned_repr = repr(cleaned_text[:300])
        logger.info("AUDIO_DEBUG: raw_text_repr = %s", raw_repr)
        logger.info("AUDIO_DEBUG: cleaned_text_repr = %s", cleaned_repr)

        chunks = split_text_for_tts(text, self.max_chunk_chars)
        
        first_chunk_repr = repr(chunks[0][:300]) if chunks else "None"
        logger.info("AUDIO_DEBUG: first_chunk_repr = %s", first_chunk_repr)

        spoken_count = 0

        logger.info("AUDIO: started reading session with %d chunks", len(chunks))

        for idx, chunk in enumerate(chunks):
            # Inspeciona o estado de cancelamento antes de cada bloco
            if self._is_cancelled:
                logger.info("AUDIO: playback interrupted at chunk %d/%d", idx, len(chunks))
                break

            try:
                self.backend.speak(chunk)
                spoken_count += 1
            except Exception as e:
                logger.error("AUDIO: Erro no backend durante a leitura do bloco %d: %s", idx, e)
                raise AudioReaderError(f"Erro no processamento do Audio Reader: {e}") from e

        logger.info("AUDIO: playback finished. %d/%d chunks spoken", spoken_count, len(chunks))
        return spoken_count

    def stop(self) -> None:
        """Cancela síncronamente a fila pendente e solicita parada do áudio ativo."""
        self._is_cancelled = True
        logger.info("AUDIO: stop requested")
        logger.info("AUDIO: pending queue cleared")
        
        # Parada best-effort no backend nativo
        self.backend.stop()

    def pause(self) -> None:
        """Solicita pausa do áudio."""
        self.backend.pause()

    def resume(self) -> None:
        """Solicita retomada do áudio."""
        self.backend.resume()

    def set_rate(self, rate: int) -> None:
        """Ajusta a velocidade da fala."""
        self.backend.set_rate(rate)

    def set_volume(self, volume: float) -> None:
        """Ajusta o volume do áudio."""
        self.backend.set_volume(volume)

    def list_voices(self) -> list:
        """Lista vozes disponíveis no motor."""
        return self.backend.list_voices()

    def set_voice(self, voice_id: str) -> None:
        """Ajusta a voz do áudio."""
        self.backend.set_voice(voice_id)
