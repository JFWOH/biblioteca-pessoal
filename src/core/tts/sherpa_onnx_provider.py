"""
Sherpa-ONNX TTS Provider — Tier D (Runtime/Infrastructure)

Sherpa-ONNX: Offline TTS/ASR over ONNX Runtime with broad platform support.
Best used as a packaging/runtime layer for local distribution.

ADR-006: No PyQt6 imports.
"""

import logging
import os
from typing import Optional

from src.core.tts.base_tts_provider import (
    BaseTTSProvider,
    SynthesisResult,
    TTSCapability,
    TTSProviderError,
    VoiceInfo,
)

logger = logging.getLogger(__name__)


class SherpaOnnxProvider(BaseTTSProvider):
    """TTS provider using Sherpa-ONNX (ONNX Runtime-based local TTS).

    Sherpa-ONNX provides a unified runtime for multiple TTS models
    in ONNX format, with good cross-platform support.
    """

    def __init__(self):
        self._tts = None
        self._available = False
        self._sample_rate = 22050
        self._default_voice_id: Optional[str] = None

        try:
            import sherpa_onnx  # noqa: F401
            self._available = True
            logger.info("SHERPA_ONNX: Module available")
        except ImportError:
            logger.info("SHERPA_ONNX: sherpa-onnx package not installed")

    @property
    def name(self) -> str:
        return "Sherpa-ONNX"

    @property
    def tier(self) -> str:
        return "D"

    @property
    def capabilities(self) -> set[TTSCapability]:
        return {
            TTSCapability.BASIC_SYNTHESIS,
            TTSCapability.VOICE_SELECTION,
            TTSCapability.LOW_LATENCY,
        }

    def initialize(self) -> None:
        """Initialize Sherpa-ONNX TTS with a default model."""
        if not self._available:
            return

        try:
            import sherpa_onnx

            # Try to find a VITS model in common locations
            model_path = self._find_model()
            if not model_path:
                logger.warning("SHERPA_ONNX: No ONNX model found")
                return

            tts_config = sherpa_onnx.OfflineTtsConfig(
                model=sherpa_onnx.OfflineTtsModelConfig(
                    vits=sherpa_onnx.OfflineTtsVitsModelConfig(
                        model=model_path,
                    ),
                ),
            )

            self._tts = sherpa_onnx.OfflineTts(tts_config)
            self._sample_rate = self._tts.sample_rate
            logger.info("SHERPA_ONNX: Initialized with model at %s", model_path)

        except Exception as e:
            logger.warning("SHERPA_ONNX: Initialization failed: %s", e)
            self._tts = None

    def health_check(self) -> bool:
        if not self._available:
            return False
        if self._tts is None:
            try:
                self.initialize()
            except Exception:
                return False
        return self._tts is not None

    def synthesize(self, text: str, voice_id: Optional[str] = None,
                   rate: float = 1.0, volume: float = 1.0) -> SynthesisResult:
        """Synthesize text using Sherpa-ONNX."""
        if not self.health_check():
            return SynthesisResult(
                error="Sherpa-ONNX not initialized",
                provider_name=self.name,
            )

        try:
            sid = int(voice_id) if voice_id and voice_id.isdigit() else 0
            audio = self._tts.generate(
                text,
                sid=sid,
                speed=rate,
            )

            if not audio.samples or len(audio.samples) == 0:
                return SynthesisResult(
                    error="Sherpa-ONNX produced no audio",
                    provider_name=self.name,
                )

            samples = list(audio.samples)
            if volume != 1.0:
                samples = [s * volume for s in samples]

            wav_data = self._samples_to_wav(samples, audio.sample_rate)

            return SynthesisResult(
                audio_data=wav_data,
                sample_rate=audio.sample_rate,
                format="wav",
                provider_name=self.name,
            )

        except Exception as e:
            logger.error("SHERPA_ONNX: Synthesis failed: %s", e)
            return SynthesisResult(
                error=f"Sherpa-ONNX synthesis failed: {e}",
                provider_name=self.name,
            )

    def speak_blocking(self, text: str, voice_id: Optional[str] = None,
                       rate: float = 1.0, volume: float = 1.0) -> None:
        """Synthesize and play blocking."""
        result = self.synthesize(text, voice_id, rate, volume)
        if not result.success:
            raise TTSProviderError(result.error or "Sherpa-ONNX synthesis failed")

        self._play_wav_blocking(result.audio_data, result.sample_rate)

    def stop(self) -> None:
        logger.info("SHERPA_ONNX: Stop requested")

    def available_voices(self) -> list[VoiceInfo]:
        return [
            VoiceInfo("0", "Default Voice", "pt-BR", "neutral",
                      "Default Sherpa-ONNX voice", ["serene"]),
        ]

    def set_default_voice(self, voice_id: str) -> None:
        self._default_voice_id = voice_id

    def latency_profile(self) -> str:
        return "low"

    def shutdown(self) -> None:
        self._tts = None
        logger.info("SHERPA_ONNX: Shutdown complete")

    # ── Internal ──────────────────────────────────────────────────────

    @staticmethod
    def _find_model() -> Optional[str]:
        """Try to find a Sherpa-ONNX compatible model."""
        search_dirs = [
            os.path.expanduser("~/.local/share/sherpa-onnx/models"),
            os.path.expanduser("~/sherpa-onnx-models"),
            "data/tts_models",
        ]
        for d in search_dirs:
            if os.path.isdir(d):
                for f in os.listdir(d):
                    if f.endswith(".onnx") and "vits" in f.lower():
                        return os.path.join(d, f)
        return None

    @staticmethod
    def _samples_to_wav(samples: list, sample_rate: int) -> bytes:
        """Convert float samples to WAV bytes."""
        import struct
        pcm_data = b""
        for s in samples:
            clamped = max(-1.0, min(1.0, float(s)))
            pcm_data += struct.pack("<h", int(clamped * 32767))

        data_size = len(pcm_data)
        header = struct.pack(
            "<4sI4s4sIHHIIHH4sI",
            b"RIFF", 36 + data_size, b"WAVE", b"fmt ",
            16, 1, 1, sample_rate, sample_rate * 2, 2, 16,
            b"data", data_size,
        )
        return header + pcm_data

    @staticmethod
    def _play_wav_blocking(wav_data: bytes, sample_rate: int) -> None:
        """Play WAV bytes blocking."""
        try:
            import sounddevice as sd
            import numpy as np
            pcm = np.frombuffer(wav_data[44:], dtype=np.int16).astype(np.float32) / 32767.0
            sd.play(pcm, samplerate=sample_rate)
            sd.wait()
            return
        except ImportError:
            pass

        import tempfile
        tmp_path = None
        try:
            with tempfile.NamedTemporaryFile(suffix=".wav", delete=False) as f:
                f.write(wav_data)
                tmp_path = f.name
            if os.name == 'nt':
                import winsound
                winsound.PlaySound(tmp_path, winsound.SND_FILENAME)
            else:
                os.system(f'aplay "{tmp_path}" 2>/dev/null || afplay "{tmp_path}" 2>/dev/null')
        finally:
            if tmp_path:
                try:
                    os.unlink(tmp_path)
                except Exception:
                    pass
