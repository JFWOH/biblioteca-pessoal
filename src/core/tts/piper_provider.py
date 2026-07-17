"""
Piper TTS Provider — Tier C (Lightweight Fallback)

Piper: Fast ONNX-based TTS, CPU-friendly, very low latency.
Ideal as robust fallback when higher-quality engines are unavailable.

ADR-006: No PyQt6 imports.
"""

import logging
import os
import subprocess
import tempfile
from typing import Optional

from src.core.tts.base_tts_provider import (
    BaseTTSProvider,
    SynthesisResult,
    TTSCapability,
    TTSProviderError,
    VoiceInfo,
)

logger = logging.getLogger(__name__)


class PiperProvider(BaseTTSProvider):
    """TTS provider using Piper (fast ONNX-based local TTS).

    Piper can be used either as:
    1. A Python library (piper-tts / piper-phonemize)
    2. A CLI binary (piper executable)

    This provider tries the Python API first, then falls back to CLI.
    """

    def __init__(self):
        self._piper_module = None
        self._piper_cli_path: Optional[str] = None
        self._model_path: Optional[str] = None
        self._default_voice_id: Optional[str] = None
        self._available = False
        self._loaded_voices = {}

        # Try Python API
        try:
            import piper  # noqa: F401
            self._piper_module = piper
            self._available = True
            logger.info("PIPER: Python module available")
        except ImportError:
            # Try CLI fallback
            self._piper_cli_path = self._find_piper_cli()
            if self._piper_cli_path:
                self._available = True
                logger.info("PIPER: CLI available at %s", self._piper_cli_path)
            else:
                logger.info("PIPER: Neither Python module nor CLI found")

    @property
    def name(self) -> str:
        return "Piper"

    @property
    def tier(self) -> str:
        return "C"

    @property
    def capabilities(self) -> set[TTSCapability]:
        return {
            TTSCapability.BASIC_SYNTHESIS,
            TTSCapability.VOICE_SELECTION,
            TTSCapability.LOW_LATENCY,
        }

    @property
    def sample_rate(self) -> int:
        return 22050

    @property
    def dtype(self) -> str:
        return 'int16'

    @property
    def channels(self) -> int:
        return 1

    def health_check(self) -> bool:
        if not self._available:
            return False
        model_path = self._model_path or self._find_default_model()
        return model_path is not None and os.path.exists(model_path)

    def synthesize(self, text: str, voice_id: Optional[str] = None,
                   rate: float = 1.0, volume: float = 1.0) -> SynthesisResult:
        """Synthesize text to WAV using Piper."""
        if not self._available:
            return SynthesisResult(
                error="Piper not available",
                provider_name=self.name,
            )

        try:
            if self._piper_module:
                return self._synthesize_python(text, voice_id, rate, volume)
            elif self._piper_cli_path:
                return self._synthesize_cli(text, voice_id, rate, volume)
            else:
                return SynthesisResult(
                    error="No Piper backend configured",
                    provider_name=self.name,
                )
        except Exception as e:
            logger.error("PIPER: Synthesis failed: %s", e)
            return SynthesisResult(
                error=f"Piper synthesis failed: {e}",
                provider_name=self.name,
            )

    def speak_blocking(self, text: str, voice_id: Optional[str] = None,
                       rate: float = 1.0, volume: float = 1.0) -> None:
        """Synthesize and play blocking."""
        result = self.synthesize(text, voice_id, rate, volume)
        if not result.success:
            raise TTSProviderError(result.error or "Piper synthesis failed")

        self._play_wav_blocking(result.audio_data)

    def stop(self) -> None:
        logger.info("PIPER: Stop requested")

    def available_voices(self) -> list[VoiceInfo]:
        """List Piper voices.

        Quando há modelos ``.onnx`` instalados, lista SOMENTE os presentes
        (item 3): anunciar uma voz que não está instalada faria o roteador
        "resolver" p.ex. a voz pt_BR e depois sintetizar no idioma errado (o
        modelo realmente carregado é o único ``.onnx`` encontrado). Sem
        diretório de modelos (ambiente de teste / Piper não configurado),
        devolve o catálogo comum como referência (ADR-005, degradação graciosa).
        """
        catalog = [
            VoiceInfo("pt_BR-faber-medium", "Faber (PT-BR)", "pt-BR", "male",
                      "Brazilian Portuguese male voice", ["serene"]),
            VoiceInfo("en_US-lessac-medium", "Lessac (EN-US)", "en-US", "female",
                      "English female voice, medium quality", ["didactic"]),
            VoiceInfo("en_US-amy-medium", "Amy (EN-US)", "en-US", "female",
                      "English female voice", ["serene"]),
            VoiceInfo("en_GB-alan-medium", "Alan (EN-GB)", "en-GB", "male",
                      "British English male voice", ["technical"]),
        ]
        installed = self._installed_model_ids()
        if installed is None:
            return catalog
        return [v for v in catalog if v.voice_id in installed]

    def set_default_voice(self, voice_id: str) -> None:
        self._default_voice_id = voice_id

    def latency_profile(self) -> str:
        return "low"

    def shutdown(self) -> None:
        self._piper_module = None
        self._loaded_voices.clear()
        logger.info("PIPER: Shutdown complete")

    # ── Internal ──────────────────────────────────────────────────────

    def _synthesize_python(self, text: str, voice_id: Optional[str],
                           rate: float, volume: float) -> SynthesisResult:
        """Use Piper Python API for synthesis."""
        try:
            from piper import PiperVoice

            model_path = self._model_path or self._find_default_model()
            if not model_path:
                return SynthesisResult(
                    error="No Piper model found",
                    provider_name=self.name,
                )

            if model_path not in self._loaded_voices:
                logger.info("PIPER: Loading model %s into cache", model_path)
                self._loaded_voices[model_path] = PiperVoice.load(model_path)

            voice = self._loaded_voices[model_path]

            import io
            import wave

            wav_io = io.BytesIO()
            with wave.open(wav_io, 'wb') as wav_file:
                voice.synthesize(text, wav_file, length_scale=1.0 / rate)

            wav_data = wav_io.getvalue()

            return SynthesisResult(
                audio_data=wav_data,
                sample_rate=22050,
                format="wav",
                provider_name=self.name,
            )
        except Exception as e:
            return SynthesisResult(
                error=f"Piper Python synthesis error: {e}",
                provider_name=self.name,
            )

    def _synthesize_cli(self, text: str, voice_id: Optional[str],
                        rate: float, volume: float) -> SynthesisResult:
        """Use Piper CLI for synthesis."""
        try:
            with tempfile.NamedTemporaryFile(suffix=".wav", delete=False) as f:
                out_path = f.name

            cmd = [self._piper_cli_path, "--output_file", out_path]

            if self._model_path:
                cmd.extend(["--model", self._model_path])

            if rate != 1.0:
                cmd.extend(["--length_scale", str(1.0 / rate)])

            process = subprocess.run(
                cmd,
                input=text.encode("utf-8"),
                capture_output=True,
                timeout=30,
            )

            if process.returncode != 0:
                return SynthesisResult(
                    error=f"Piper CLI error: {process.stderr.decode('utf-8', errors='replace')}",
                    provider_name=self.name,
                )

            with open(out_path, "rb") as f:
                wav_data = f.read()

            return SynthesisResult(
                audio_data=wav_data,
                sample_rate=22050,
                format="wav",
                provider_name=self.name,
            )
        except Exception as e:
            return SynthesisResult(
                error=f"Piper CLI error: {e}",
                provider_name=self.name,
            )
        finally:
            try:
                os.unlink(out_path)
            except Exception:
                pass

    @staticmethod
    def _find_piper_cli() -> Optional[str]:
        """Try to find piper executable on PATH."""
        import shutil
        path = shutil.which("piper")
        if path:
            return path
        # Common Windows locations
        common_paths = [
            os.path.expanduser("~/.local/bin/piper"),
            os.path.expanduser("~/piper/piper.exe"),
            "C:/piper/piper.exe",
        ]
        for p in common_paths:
            if os.path.isfile(p):
                return p
        return None

    @staticmethod
    def _model_dirs() -> list[str]:
        return [
            os.path.expanduser("~/.local/share/piper-tts/models"),
            os.path.expanduser("~/piper-models"),
        ]

    @staticmethod
    def _find_default_model() -> Optional[str]:
        """Try to find a default Piper model."""
        for d in PiperProvider._model_dirs():
            if os.path.isdir(d):
                for f in os.listdir(d):
                    if f.endswith(".onnx"):
                        return os.path.join(d, f)
        return None

    @staticmethod
    def _installed_model_ids() -> Optional[set[str]]:
        """IDs de voz (basename sem ``.onnx``) dos modelos Piper instalados.

        Retorna ``None`` quando não há nenhum ``.onnx`` para inspecionar (não
        sabemos o que está instalado ⇒ não filtramos o catálogo). Retorna um
        conjunto (possivelmente parcial) quando encontramos modelos.
        """
        found: Optional[set[str]] = None
        for d in PiperProvider._model_dirs():
            if os.path.isdir(d):
                for f in os.listdir(d):
                    if f.endswith(".onnx"):
                        if found is None:
                            found = set()
                        found.add(f[: -len(".onnx")])
        return found

    @staticmethod
    def _play_wav_blocking(wav_data: bytes) -> None:
        """Play WAV data blocking."""
        try:
            import sounddevice as sd
            import numpy as np
            pcm = np.frombuffer(wav_data[44:], dtype=np.int16).astype(np.float32) / 32767.0
            sd.play(pcm, samplerate=22050)
            sd.wait()
            return
        except ImportError:
            pass

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
