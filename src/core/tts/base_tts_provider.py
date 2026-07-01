"""
Base TTS Provider — Unified abstraction for local text-to-speech backends.

Defines the contract that all TTS providers (Kokoro, Piper, Qwen3-TTS,
Sherpa-ONNX, pyttsx3 legacy) must implement.

ADR-006 compliance: This module MUST NOT import PyQt6 or GUI modules.
ADR-007 compliance: Extends the original TTSBackend concept with richer
    capability detection, streaming support, and voice profile awareness.
"""

from abc import ABC, abstractmethod
from dataclasses import dataclass, field
from enum import Enum, auto
from typing import Optional
import logging

logger = logging.getLogger(__name__)


class TTSProviderError(Exception):
    """Base exception for TTS provider errors."""
    pass


class TTSProviderUnavailable(TTSProviderError):
    """Raised when a TTS provider cannot be initialized on this system."""
    pass


class TTSCapability(Enum):
    """Capabilities that a TTS provider may support."""
    BASIC_SYNTHESIS = auto()
    STREAMING = auto()
    VOICE_SELECTION = auto()
    RATE_CONTROL = auto()
    VOLUME_CONTROL = auto()
    EXPRESSIVENESS_CONTROL = auto()
    MULTILINGUAL = auto()
    LOW_LATENCY = auto()


@dataclass
class VoiceInfo:
    """Describes a single voice available in a provider."""
    voice_id: str
    name: str
    language: str = "pt-BR"
    gender: str = "neutral"
    description: str = ""
    tags: list[str] = field(default_factory=list)


@dataclass
class SynthesisResult:
    """Result of a synthesis operation."""
    audio_data: Optional[bytes] = None
    sample_rate: int = 22050
    format: str = "wav"
    provider_name: str = ""
    was_fallback: bool = False
    error: Optional[str] = None

    @property
    def success(self) -> bool:
        return self.audio_data is not None and self.error is None


class BaseTTSProvider(ABC):
    """Abstract base class for all TTS providers.

    Each provider wraps a specific local TTS engine and exposes
    a uniform interface for synthesis, voice listing, and health checks.

    Providers MUST:
    - Not import PyQt6 or any GUI module (ADR-006).
    - Handle their own dependency checks in __init__.
    - Raise TTSProviderUnavailable if dependencies are missing.
    - Implement graceful error handling (ADR-005).
    """

    # ── Identity ──────────────────────────────────────────────────────

    @property
    @abstractmethod
    def name(self) -> str:
        """Human-readable name of this provider (e.g., 'Kokoro', 'Piper')."""
        ...

    @property
    @abstractmethod
    def tier(self) -> str:
        """Quality/weight tier: 'A' (best), 'B' (default), 'C' (fallback), 'D' (runtime)."""
        ...

    @property
    def capabilities(self) -> set[TTSCapability]:
        """Set of capabilities this provider supports."""
        return {TTSCapability.BASIC_SYNTHESIS}

    @property
    def sample_rate(self) -> int:
        """Sample rate of the synthesized audio (e.g. 24000)."""
        return 22050

    @property
    def dtype(self) -> str:
        """Data type of the raw audio samples (e.g. 'int16', 'float32')."""
        return 'int16'

    @property
    def channels(self) -> int:
        """Number of audio channels (e.g. 1 for mono, 2 for stereo)."""
        return 1

    # ── Core Contract ─────────────────────────────────────────────────

    @abstractmethod
    def synthesize(self, text: str, voice_id: Optional[str] = None,
                   rate: float = 1.0, volume: float = 1.0) -> SynthesisResult:
        """Synthesize text to audio.

        Args:
            text: Pre-processed text ready for synthesis.
            voice_id: Optional voice identifier. If None, uses default voice.
            rate: Speech rate multiplier (1.0 = normal).
            volume: Volume level 0.0–1.0.

        Returns:
            SynthesisResult with audio_data on success, or error details.
        """
        ...

    def synthesize_stream(self, text: str, voice_id: Optional[str] = None,
                          rate: float = 1.0, volume: float = 1.0):
        """Yields SynthesisResult objects as audio segments are generated.

        Default implementation just yields a single SynthesisResult from synthesize().
        """
        yield self.synthesize(text, voice_id, rate, volume)

    @abstractmethod
    def speak_blocking(self, text: str, voice_id: Optional[str] = None,
                       rate: float = 1.0, volume: float = 1.0) -> None:
        """Synthesize and play text synchronously (blocks until done).

        This is the compatibility path for providers that don't separate
        synthesis from playback (e.g., pyttsx3). Modern providers should
        implement synthesize() and use the audio pipeline for playback.
        """
        ...

    @abstractmethod
    def stop(self) -> None:
        """Cancel any ongoing synthesis/playback (best-effort)."""
        ...

    # ── Voice Management ──────────────────────────────────────────────

    def available_voices(self) -> list[VoiceInfo]:
        """List voices available in this provider."""
        return []

    def set_default_voice(self, voice_id: str) -> None:
        """Set the default voice for this provider."""
        pass

    # ── Health & Capability Detection ─────────────────────────────────

    def health_check(self) -> bool:
        """Returns True if the provider is ready to synthesize.

        Should be fast and non-blocking. Used by the router to skip
        unhealthy providers during fallback.
        """
        return True

    def supports_streaming(self) -> bool:
        """Returns True if the provider supports streaming synthesis."""
        return TTSCapability.STREAMING in self.capabilities

    def latency_profile(self) -> str:
        """Returns a latency classification: 'low', 'medium', 'high'."""
        return "medium"

    # ── Lifecycle ─────────────────────────────────────────────────────

    def initialize(self) -> None:
        """Optional lazy initialization hook.

        Called by the router before first use. Providers that need
        heavy setup (model loading, etc.) should do it here rather
        than in __init__.
        """
        pass

    def shutdown(self) -> None:
        """Optional cleanup hook. Called when the router shuts down."""
        pass

    def __repr__(self) -> str:
        return f"<{self.__class__.__name__} name='{self.name}' tier='{self.tier}'>"
