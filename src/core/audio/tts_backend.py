from abc import ABC, abstractmethod

class AudioReaderError(Exception):
    """Exception base do domínio do Audio Reader."""
    pass

class TTSBackendUnavailable(AudioReaderError):
    """Lançada quando um backend de TTS está indisponível no sistema atual."""
    pass

class TTSBackend(ABC):
    """Interface abstrata para backends de Text-to-Speech (TTS)."""

    @abstractmethod
    def speak(self, text: str) -> None:
        """Executa a leitura em voz alta do texto fornecido.
        
        Deve ser uma operação síncrona/bloqueante que processa o texto no motor.
        """
        pass

    @abstractmethod
    def stop(self) -> None:
        """Cancela e interrompe imediatamente a reprodução do áudio atual (best-effort)."""
        pass

    def pause(self) -> None:
        """Pausa a reprodução do áudio atual. (Opcional, no-op por padrão)"""
        pass

    def resume(self) -> None:
        """Retoma a reprodução do áudio pausado. (Opcional, no-op por padrão)"""
        pass

    def set_rate(self, rate: int) -> None:
        """Ajusta a velocidade da fala (palavras por minuto). (Opcional, no-op por padrão)"""
        pass

    def set_volume(self, volume: float) -> None:
        """Ajusta o volume da fala (de 0.0 a 1.0). (Opcional, no-op por padrão)"""
        pass

    def list_voices(self) -> list:
        """Lista as vozes disponíveis no backend. Retorna lista vazia por padrão."""
        return []

    def set_voice(self, voice_id: str) -> None:
        """Define a voz a ser utilizada a partir do identificador. (Opcional, no-op por padrão)"""
        pass
