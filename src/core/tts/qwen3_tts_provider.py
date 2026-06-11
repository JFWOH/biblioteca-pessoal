"""
Qwen3-TTS Provider — Tier A (Advanced Optional)

Qwen3-TTS: Multi-lingual (10 languages including Portuguese), expressive,
streaming-capable, instruction-controlled. Models range from ~0.6B to ~1.7B.

This is the advanced/optional tier — only used when hardware supports it.

ADR-006: No PyQt6 imports.
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


class Qwen3TTSProvider(BaseTTSProvider):
    """TTS provider using Qwen3-TTS (advanced neural TTS).

    Qwen3-TTS offers:
    - Multilingual support (10 languages incl. Portuguese)
    - Instruction-based control of expressiveness
    - Streaming synthesis
    - Robust handling of noisy text

    Requires: transformers, torch, and the Qwen3-TTS model weights.
    """

    def __init__(self):
        self._model = None
        self._processor = None
        self._available = False
        self._default_voice_id: Optional[str] = None

        # Check dependencies
        try:
            import torch  # noqa: F401
            import transformers  # noqa: F401
            self._available = True
        except ImportError as e:
            logger.info("QWEN3_TTS: Dependencies not available: %s", e)
            self._available = False

    @property
    def name(self) -> str:
        return "Qwen3-TTS"

    @property
    def tier(self) -> str:
        return "A"

    @property
    def capabilities(self) -> set[TTSCapability]:
        return {
            TTSCapability.BASIC_SYNTHESIS,
            TTSCapability.STREAMING,
            TTSCapability.VOICE_SELECTION,
            TTSCapability.RATE_CONTROL,
            TTSCapability.EXPRESSIVENESS_CONTROL,
            TTSCapability.MULTILINGUAL,
        }

    def initialize(self) -> None:
        """Load the Qwen3-TTS model (heavy operation)."""
        if not self._available:
            return

        try:
            # Model name is a placeholder for the advanced tier architecture.
            # Avoid hitting the HuggingFace API during auto-registration.
            model_name = "Qwen/Qwen2-Audio-7B-Instruct"  # Placeholder
            
            # TODO: Only load this heavy model if explicitly configured by the user.
            # For Phase 13, this is an architectural stub.
            self._model = None
            self._processor = None
            
        except Exception as e:
            logger.warning("QWEN3_TTS: Failed to load model: %s", e)
            self._model = None
            self._processor = None

    def health_check(self) -> bool:
        """Qwen3-TTS requires explicit initialization due to model weight."""
        if not self._available:
            return False
        # Don't auto-initialize — model is heavy. Return True only if already loaded.
        return self._model is not None and self._processor is not None

    def synthesize(self, text: str, voice_id: Optional[str] = None,
                   rate: float = 1.0, volume: float = 1.0) -> SynthesisResult:
        """Synthesize text using Qwen3-TTS."""
        if not self.health_check():
            return SynthesisResult(
                error="Qwen3-TTS model not loaded",
                provider_name=self.name,
            )

        try:
            import torch
            import struct

            # Build instruction prompt for expressiveness
            instruction = self._build_instruction(voice_id, rate)

            inputs = self._processor(
                f"<|tts|>{instruction}\n{text}",
                return_tensors="pt",
            )

            if torch.cuda.is_available():
                inputs = {k: v.cuda() for k, v in inputs.items()}

            with torch.no_grad():
                outputs = self._model.generate(
                    **inputs,
                    max_new_tokens=4096,
                    do_sample=True,
                    temperature=0.7,
                )

            # Extract audio tokens and decode to waveform
            audio_tokens = outputs[0][inputs["input_ids"].shape[1]:]

            # Convert tokens to audio samples (model-specific decoding)
            samples = self._decode_audio_tokens(audio_tokens)

            if not samples:
                return SynthesisResult(
                    error="Qwen3-TTS produced no audio",
                    provider_name=self.name,
                )

            # Apply volume
            if volume != 1.0:
                samples = [s * volume for s in samples]

            wav_data = self._samples_to_wav(samples, 24000)

            return SynthesisResult(
                audio_data=wav_data,
                sample_rate=24000,
                format="wav",
                provider_name=self.name,
            )

        except Exception as e:
            logger.error("QWEN3_TTS: Synthesis failed: %s", e)
            return SynthesisResult(
                error=f"Qwen3-TTS synthesis failed: {e}",
                provider_name=self.name,
            )

    def speak_blocking(self, text: str, voice_id: Optional[str] = None,
                       rate: float = 1.0, volume: float = 1.0) -> None:
        """Synthesize and play blocking."""
        result = self.synthesize(text, voice_id, rate, volume)
        if not result.success:
            raise TTSProviderError(result.error or "Qwen3-TTS synthesis failed")

        self._play_wav_blocking(result.audio_data, result.sample_rate)

    def stop(self) -> None:
        logger.info("QWEN3_TTS: Stop requested")

    def available_voices(self) -> list[VoiceInfo]:
        return [
            VoiceInfo("serene_narrator", "Serene Narrator", "pt-BR", "neutral",
                      "Calm, steady narration voice (instruction-controlled)", ["serene"]),
            VoiceInfo("didactic_assistant", "Didactic Assistant", "pt-BR", "neutral",
                      "Clear, instructional voice", ["didactic"]),
            VoiceInfo("expressive_reader", "Expressive Reader", "pt-BR", "neutral",
                      "Emotionally nuanced voice for fiction", ["expressive"]),
        ]

    def set_default_voice(self, voice_id: str) -> None:
        self._default_voice_id = voice_id

    def latency_profile(self) -> str:
        return "high"

    def supports_streaming(self) -> bool:
        return True

    def shutdown(self) -> None:
        self._model = None
        self._processor = None
        logger.info("QWEN3_TTS: Shutdown complete")

    # ── Internal Helpers ──────────────────────────────────────────────

    @staticmethod
    def _build_instruction(voice_id: Optional[str], rate: float) -> str:
        """Build an instruction prompt for Qwen3-TTS expressiveness control."""
        style = "calm and steady" if not voice_id else {
            "serene_narrator": "calm, warm, and steady with gentle pacing",
            "didactic_assistant": "clear, precise, and slightly faster",
            "expressive_reader": "emotionally nuanced with natural variation",
        }.get(voice_id, "neutral and natural")

        speed = "normal" if 0.9 <= rate <= 1.1 else (
            "slightly faster" if rate > 1.1 else "slightly slower"
        )

        return f"Read the following text in a {style} manner at {speed} speed."

    @staticmethod
    def _decode_audio_tokens(tokens) -> list[float]:
        """Decode model output tokens to audio samples.

        This is a simplified placeholder — real implementation depends
        on the specific Qwen3-TTS codec/vocoder being used.
        """
        # In a real implementation, this would use the model's audio codec
        # to convert discrete tokens back to a continuous waveform.
        # For now, return empty to signal that synthesis needs the full pipeline.
        return []

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

        import tempfile, os
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
