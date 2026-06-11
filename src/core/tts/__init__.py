"""
src.core.tts — Unified TTS Provider Layer (Phase 13)

Provides a backend-agnostic abstraction for local text-to-speech synthesis,
supporting multiple engines with automatic capability detection and fallback.
"""

from src.core.tts.base_tts_provider import (
    BaseTTSProvider,
    TTSProviderError,
    TTSProviderUnavailable,
    TTSCapability,
    SynthesisResult,
)
from src.core.tts.voice_profile import VoiceProfile, NarrationRole
from src.core.tts.tts_router import TTSRouter
from src.core.tts.text_preprocessor import TTSTextPreprocessor

__all__ = [
    "BaseTTSProvider",
    "TTSProviderError",
    "TTSProviderUnavailable",
    "TTSCapability",
    "SynthesisResult",
    "VoiceProfile",
    "NarrationRole",
    "TTSRouter",
    "TTSTextPreprocessor",
]
