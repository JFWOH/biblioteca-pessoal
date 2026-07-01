"""
pyttsx3 Legacy TTS Provider — Ultimate Fallback

Adapter wrapping the existing Pyttsx3Backend from src/core/audio
to conform to the new BaseTTSProvider interface.

This ensures the app always has at least one working TTS backend,
even if no modern engine (Kokoro, Piper, etc.) is installed.

ADR-006: No PyQt6 imports.
ADR-007: Preserves the existing audio reader contract.
"""

import logging
from typing import Optional

from src.core.tts.base_tts_provider import (
    BaseTTSProvider,
    SynthesisResult,
    TTSCapability,
    TTSProviderError,
    TTSProviderUnavailable,
    VoiceInfo,
)

logger = logging.getLogger(__name__)


class Pyttsx3Provider(BaseTTSProvider):
    """TTS provider wrapping the legacy pyttsx3 backend.

    Delegates to the existing Pyttsx3Backend from src/core/audio/
    for full backward compatibility. This is the ultimate fallback
    that works on any Windows system with SAPI5.
    """

    def __init__(self):
        self._backend = None
        self._available = False
        self._default_voice_id: Optional[str] = None

        try:
            from src.core.audio.pyttsx3_backend import Pyttsx3Backend
            self._backend = Pyttsx3Backend()
            self._available = True
        except Exception as e:
            logger.info("PYTTSX3_PROVIDER: pyttsx3 not available: %s", e)

    @property
    def name(self) -> str:
        return "pyttsx3"

    @property
    def tier(self) -> str:
        return "legacy"

    @property
    def capabilities(self) -> set[TTSCapability]:
        return {
            TTSCapability.BASIC_SYNTHESIS,
            TTSCapability.VOICE_SELECTION,
            TTSCapability.RATE_CONTROL,
            TTSCapability.VOLUME_CONTROL,
        }

    def health_check(self) -> bool:
        return self._available and self._backend is not None

    def synthesize(self, text: str, voice_id: Optional[str] = None,
                   rate: float = 1.0, volume: float = 1.0) -> SynthesisResult:
        """pyttsx3 doesn't separate synthesis from playback.

        Returns a placeholder result — use speak_blocking() instead.
        """
        return SynthesisResult(
            error="pyttsx3 does not support separate synthesis; use speak_blocking()",
            provider_name=self.name,
        )

    def speak_blocking(self, text: str, voice_id: Optional[str] = None,
                       rate: float = 1.0, volume: float = 1.0) -> None:
        """Synthesize and play using pyttsx3 (blocking)."""
        if not self.health_check():
            raise TTSProviderUnavailable("pyttsx3 backend not available")

        # Apply settings
        pyttsx3_rate = int(180 * rate)  # Base rate 180 wpm * multiplier
        self._backend.set_rate(pyttsx3_rate)
        self._backend.set_volume(volume)

        if voice_id:
            self._backend.set_voice(voice_id)
        elif self._default_voice_id:
            self._backend.set_voice(self._default_voice_id)

        try:
            self._backend.speak(text)
        except Exception as e:
            raise TTSProviderError(f"pyttsx3 speak failed: {e}") from e

    def stop(self) -> None:
        if self._backend:
            self._backend.stop()

    def available_voices(self) -> list[VoiceInfo]:
        if not self._backend:
            return []

        raw_voices = self._backend.list_voices()
        result = []
        for v in raw_voices:
            result.append(VoiceInfo(
                voice_id=v.get("id", ""),
                name=v.get("name", "Unknown"),
                language=str(v.get("languages", ["unknown"])[0]) if v.get("languages") else "unknown",
                gender="neutral",
                description="System SAPI voice",
                tags=["legacy"],
            ))
        return result

    def set_default_voice(self, voice_id: str) -> None:
        self._default_voice_id = voice_id
        if self._backend:
            self._backend.set_voice(voice_id)

    def latency_profile(self) -> str:
        return "low"

    def shutdown(self) -> None:
        self._backend = None
        logger.info("PYTTSX3_PROVIDER: Shutdown complete")
