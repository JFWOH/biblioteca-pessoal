"""
Kokoro TTS Provider — Tier B (MVP Default Quality)

Kokoro-82M: 82M parameters, Apache-2.0 license, high naturalness,
low footprint. Best for serene narration and comfortable long reading.

ADR-006: No PyQt6 imports.
"""

import logging
import os
os.environ["HF_HUB_OFFLINE"] = "1"
os.environ["HF_HUB_DISABLE_SYMLINKS_WARNING"] = "1"
import time
from typing import Optional

# Record environment variables at process/module start
HF_ENV_AT_PROCESS_START = os.environ.get("HF_HUB_OFFLINE", "Not Set")
HF_HOME_START = os.environ.get("HF_HOME", "Not Set")
HF_HUB_CACHE_START = os.environ.get("HF_HUB_CACHE", "Not Set")

def check_kokoro_cache_materialized() -> bool:
    """Robustly verify if the Kokoro model files are cached locally."""
    hf_hub_cache = os.environ.get("HF_HUB_CACHE")
    if not hf_hub_cache:
        hf_home = os.environ.get("HF_HOME")
        if hf_home:
            hf_hub_cache = os.path.join(hf_home, "hub")
        else:
            hf_hub_cache = os.path.expanduser("~/.cache/huggingface/hub")
            
    model_dir = os.path.join(hf_hub_cache, "models--hexgrad--Kokoro-82M")
    if not os.path.exists(model_dir):
        return False
        
    snapshots_dir = os.path.join(model_dir, "snapshots")
    if not os.path.exists(snapshots_dir):
        return False
        
    try:
        snapshots = os.listdir(snapshots_dir)
        if not snapshots:
            return False
        for snapshot in snapshots:
            snap_path = os.path.join(snapshots_dir, snapshot)
            if os.path.isdir(snap_path):
                config_path = os.path.join(snap_path, "config.json")
                pth_path = os.path.join(snap_path, "kokoro-v1_0.pth")
                voices_dir = os.path.join(snap_path, "voices")
                if os.path.exists(config_path) and os.path.exists(pth_path) and os.path.exists(voices_dir):
                    return True
    except Exception:
        pass
    return False

# Set HF_HUB_OFFLINE to 1 unconditionally BEFORE importing kokoro to prevent any network hangs
KOKORO_CACHE_HIT = check_kokoro_cache_materialized()
os.environ["HF_HUB_OFFLINE"] = "1"

HF_HUB_OFFLINE_AT_IMPORT = os.environ.get("HF_HUB_OFFLINE", "Not Set")

from src.core.tts.base_tts_provider import (  # noqa: E402 — HF_HUB_OFFLINE precisa ser setado ANTES dos imports
    BaseTTSProvider,
    SynthesisResult,
    TTSCapability,
    TTSProviderError,
    TTSProviderUnavailable,
    VoiceInfo,
)

logger = logging.getLogger(__name__)
logger.info("HF_ENV_AT_PROCESS_START: %s", HF_ENV_AT_PROCESS_START)
logger.info("HF_HUB_OFFLINE_AT_IMPORT: %s", HF_HUB_OFFLINE_AT_IMPORT)
logger.info("HF_HOME: %s", HF_HOME_START)
logger.info("HF_HUB_CACHE: %s", HF_HUB_CACHE_START)
logger.info("KOKORO_CACHE_HIT: %s", KOKORO_CACHE_HIT)
logger.info("KOKORO_CACHE_MISS: %s", not KOKORO_CACHE_HIT)



class KokoroProvider(BaseTTSProvider):
    """TTS provider using Kokoro (local neural TTS).

    Kokoro is a lightweight neural TTS engine with high naturalness.
    This provider wraps the kokoro library if installed.
    """

    def __init__(self):
        self._pipelines = {}
        self._available = False
        self._default_voice_id: Optional[str] = None
        self._is_ready = False
        self._warmup_started_at = None
        self._warmup_finished_at = None
        self._last_warmup_error = None
        self._pipeline_cache_state = "cold"
        self._model_cache_hit = False
        self._model_cache_miss = True
        self._first_inference_done = False
        import threading
        self._warmup_event = threading.Event()
        self._warmup_event.set()
        self._is_cancelled = False

        try:
            import kokoro  # noqa: F401
            self._available = True
        except ImportError:
            logger.info("KOKORO: kokoro package not installed")
            self._available = False
            raise TTSProviderUnavailable("Biblioteca kokoro não está instalada ou não pode ser importada.")

        # Check cache materialization
        if not KOKORO_CACHE_HIT:
            logger.warning("KOKORO: Cache not materialized and offline mode active.")
            self._available = False
            raise TTSProviderUnavailable("Arquivos do modelo Kokoro-82M não encontrados no cache local do Hugging Face.")

        self._device = "cuda" if self._check_cuda_compatibility() else "cpu"

    def _check_cuda_compatibility(self) -> bool:
        """Check if CUDA is available and compatible with the current PyTorch install."""
        try:
            import torch
            if not torch.cuda.is_available():
                logger.info("KOKORO: CUDA is not available on this system. Using CPU.")
                return False
            
            major, minor = torch.cuda.get_device_capability(0)
            device_arch = f"sm_{major}{minor}"
            arch_list = torch.cuda.get_arch_list()
            
            if device_arch in arch_list or f"sm_{major}0" in arch_list:
                logger.info("KOKORO: CUDA is available and compatible (%s). Using CUDA.", device_arch)
                return True
                
            logger.warning(
                "KOKORO: CUDA device capability %s is not supported by current PyTorch installation (supported: %s). "
                "Forcing CPU device to prevent crashes/warnings.",
                device_arch, arch_list
            )
            return False
        except Exception as e:
            logger.warning("KOKORO: Error checking CUDA compatibility, defaulting to CPU: %s", e)
            return False

    @property
    def name(self) -> str:
        return "Kokoro"

    @property
    def tier(self) -> str:
        return "B"

    @property
    def capabilities(self) -> set[TTSCapability]:
        caps = {TTSCapability.BASIC_SYNTHESIS, TTSCapability.VOICE_SELECTION, TTSCapability.STREAMING}
        if self._available:
            caps.add(TTSCapability.RATE_CONTROL)
        return caps

    @property
    def sample_rate(self) -> int:
        return 24000

    @property
    def dtype(self) -> str:
        return 'float32'

    @property
    def channels(self) -> int:
        return 1

    def latency_profile(self) -> str:
        """Returns high latency if running on CPU, medium if on GPU."""
        return "high" if self._device == "cpu" else "medium"

    def _get_pipeline(self, lang_code: str):
        """Get or initialize a KPipeline for the specific language code."""
        if not self._available:
            return None
        if lang_code not in self._pipelines:
            try:
                import kokoro
                logger.info("KOKORO: Loading pipeline for language '%s' on device '%s'...", lang_code, self._device)
                try:
                    self._pipelines[lang_code] = kokoro.KPipeline(
                        lang_code=lang_code,
                        repo_id='hexgrad/Kokoro-82M',
                        device=self._device
                    )
                except RuntimeError as e:
                    # Fallback to CPU if CUDA is unsupported
                    if "no kernel image is available" in str(e) or "CUDA error" in str(e):
                        logger.warning("KOKORO: CUDA kernel not supported on this GPU. Falling back to CPU for pipeline '%s'...", lang_code)
                        self._pipelines[lang_code] = kokoro.KPipeline(lang_code=lang_code, repo_id='hexgrad/Kokoro-82M', device='cpu')
                    else:
                        raise e
                logger.info("KOKORO: Pipeline for '%s' loaded successfully", lang_code)
            except Exception as e:
                logger.error("KOKORO: Failed to load pipeline for '%s': %s", lang_code, e)
                # Fallback to English 'a' if another language fails to load (e.g., missing espeak-ng)
                if lang_code != "a":
                    logger.warning("KOKORO: Attempting fallback to English pipeline 'a'...")
                    return self._get_pipeline("a")
                return None
        return self._pipelines.get(lang_code)

    def _ensure_voice(self, pipeline, voice: str) -> None:
        """Garante que a voz esteja carregada, baixando-a no 1º uso.

        O Kokoro baixa o arquivo da voz sob demanda; como o processo força
        HF_HUB_OFFLINE=1, vozes ainda não cacheadas (ex.: vozes em inglês numa
        instalação nova) falhariam offline. Aqui liberamos a rede apenas ao redor
        do load da voz e restauramos em seguida — mesmo padrão do NLLB. Se a voz
        já está no cache do pipeline, é um no-op (nenhuma rede).
        """
        try:
            if voice in getattr(pipeline, "voices", {}):
                return
        except Exception:
            return
        # Libera a rede só ao redor do load da voz. NOTA: o huggingface_hub lê
        # HF_HUB_OFFLINE numa constante de módulo no import; mudar só os.environ
        # depois não tem efeito — é preciso patchar constants.HF_HUB_OFFLINE.
        import huggingface_hub.constants as hf_const
        prev_const = hf_const.HF_HUB_OFFLINE
        prev_env = os.environ.get("HF_HUB_OFFLINE")
        hf_const.HF_HUB_OFFLINE = False
        os.environ["HF_HUB_OFFLINE"] = "0"
        try:
            pipeline.load_voice(voice)
            logger.info("KOKORO: voz '%s' carregada (download no 1º uso se necessário).", voice)
        except Exception as e:
            logger.warning("KOKORO: não foi possível baixar/carregar a voz '%s': %s", voice, e)
        finally:
            hf_const.HF_HUB_OFFLINE = prev_const
            if prev_env is None:
                os.environ.pop("HF_HUB_OFFLINE", None)
            else:
                os.environ["HF_HUB_OFFLINE"] = prev_env

    def initialize(self) -> None:
        """Start a background thread to pre-warm the primary language pipeline."""
        if not self._available:
            logger.warning("KOKORO_WARMUP_FAILED: Provider is marked not available.")
            return
            
        import threading
        import time
        
        self._warmup_event.clear()
        self._is_ready = False
        self._warmup_started_at = time.time()
        logger.info("KOKORO_WARMUP_STARTED: Background pre-warm started for language 'p'")
        
        def _warmup():
            try:
                # Log import timing
                import os
                logger.info("KOKORO_IMPORT_STAGE: Starting imports...")
                import_t0 = time.time()
                logger.info("KOKORO_IMPORT_STAGE: Finished importing kokoro package in %.2fs", time.time() - import_t0)

                # Unconditionally force HuggingFace offline mode for the warmup process
                os.environ["HF_HUB_OFFLINE"] = "1"
                self._model_cache_hit = check_kokoro_cache_materialized()
                self._model_cache_miss = not self._model_cache_hit
                self._pipeline_cache_state = "cached" if self._model_cache_hit else "cold"
                logger.info("KOKORO_CACHE_STATE: hit=%s, state=%s", self._model_cache_hit, self._pipeline_cache_state)
                
                logger.info("KOKORO_PIPELINE_LOAD_STARTED: Loading Kokoro pipeline...")
                pipeline_t0 = time.time()
                pipeline = self._get_pipeline("p")
                pipeline_load_ms = (time.time() - pipeline_t0) * 1000.0
                logger.info("KOKORO_PIPELINE_LOAD_FINISHED: Kokoro pipeline loaded in %.2f ms.", pipeline_load_ms)
                logger.info("KOKORO_PIPELINE_LOAD_MS: %.2f ms", pipeline_load_ms)
                    
                if pipeline:
                    logger.info("KOKORO_WARMUP_STARTED: Running warmup inference...")
                    warmup_t0 = time.time()
                    generator = pipeline(".", voice="pf_dora")
                    for _ in generator:
                        pass
                    warmup_ms = (time.time() - warmup_t0) * 1000.0
                    logger.info("KOKORO_WARMUP_FINISHED: Warmup inference finished.")
                    logger.info("KOKORO_WARMUP_MS: %.2f ms", warmup_ms)
                    
                    self._is_ready = True
                    self._warmup_finished_at = time.time()
                    logger.info("KOKORO_READY: Kokoro is ready for synthesis.")
                else:
                    raise Exception("Pipeline could not be loaded")
            except Exception as e:
                self._last_warmup_error = str(e)
                logger.error("KOKORO_WARMUP_FAILED: Warmup failed: %s", e)
            finally:
                self._warmup_event.set()
            
        t = threading.Thread(target=_warmup, daemon=True)
        t.start()

    def health_check(self) -> bool:
        """Provider is healthy if the kokoro package is installed and importable."""
        return self._available

    def synthesize(self, text: str, voice_id: Optional[str] = None,
                   rate: float = 1.0, volume: float = 1.0) -> SynthesisResult:
        """Synthesize text to audio bytes using Kokoro."""
        if not self.health_check():
            return SynthesisResult(
                error="Kokoro model not available",
                provider_name=self.name,
            )

        if not self._is_ready:
            logger.info("KOKORO: Waiting for readiness event...")
            ready = self._warmup_event.wait(timeout=3.0)
            if not ready or not self._is_ready:
                logger.error("KOKORO_READINESS_TIMEOUT: Kokoro is not ready within timeout of 3.0s.")
                return SynthesisResult(
                    error="KOKORO_READINESS_TIMEOUT: Kokoro not ready within 3.0s timeout",
                    provider_name=self.name,
                )

        try:
            import numpy as np

            voice = voice_id or self._default_voice_id or "pf_dora"
            
            # Determine lang_code from first letter of voice ID (e.g. 'p' for 'pf_dora', 'a' for 'af_heart')
            lang_code = voice[0] if len(voice) > 0 else "p"
            
            pipeline = self._get_pipeline(lang_code)
            if not pipeline:
                return SynthesisResult(
                    error=f"Kokoro pipeline for language '{lang_code}' could not be initialized",
                    provider_name=self.name,
                )

            inference_t0 = time.time()
            self._is_cancelled = False
            self._ensure_voice(pipeline, voice)
            generator = pipeline(text, voice=voice, speed=rate)

            all_segments = []
            sample_rate = 24000

            for result in generator:
                if self._is_cancelled:
                    break
                gs, ps, audio = result
                if audio is not None:
                    all_segments.append(audio)
                    if hasattr(audio, 'sr'):
                        sample_rate = audio.sr

            inference_ms = (time.time() - inference_t0) * 1000.0
            if not self._first_inference_done:
                logger.info("KOKORO_FIRST_INFERENCE_MS: %.2f ms", inference_ms)
                self._first_inference_done = True

            if not all_segments:
                return SynthesisResult(
                    error="Kokoro produced no audio",
                    provider_name=self.name,
                )

            # Concatenate all segments using fast NumPy vectorization
            all_samples = np.concatenate(all_segments)

            # Apply volume using vectorized multiplication
            if volume != 1.0:
                all_samples = all_samples * volume

            # Convert to WAV bytes
            wav_data = self._samples_to_wav(all_samples, sample_rate)

            return SynthesisResult(
                audio_data=wav_data,
                sample_rate=sample_rate,
                format="wav",
                provider_name=self.name,
            )

        except Exception as e:
            logger.error("KOKORO: Synthesis failed: %s", e)
            return SynthesisResult(
                error=f"Kokoro synthesis failed: {e}",
                provider_name=self.name,
            )

    def synthesize_stream(self, text: str, voice_id: Optional[str] = None,
                          rate: float = 1.0, volume: float = 1.0):
        """Synthesize text and yield SynthesisResult segment-by-segment."""
        if not self.health_check():
            yield SynthesisResult(
                error="Kokoro model not available",
                provider_name=self.name,
            )
            return

        if not self._is_ready:
            logger.info("KOKORO: Waiting for readiness event...")
            ready = self._warmup_event.wait(timeout=3.0)
            if not ready or not self._is_ready:
                logger.error("KOKORO_READINESS_TIMEOUT: Kokoro not ready within 3.0s")
                yield SynthesisResult(
                    error="KOKORO_READINESS_TIMEOUT: Kokoro not ready within 3.0s",
                    provider_name=self.name,
                )
                return

        try:
            import numpy as np
            voice = voice_id or self._default_voice_id or "pf_dora"
            lang_code = voice[0] if len(voice) > 0 else "p"
            
            pipeline = self._get_pipeline(lang_code)
            if not pipeline:
                yield SynthesisResult(
                    error=f"Kokoro pipeline for language '{lang_code}' could not be initialized",
                    provider_name=self.name,
                )
                return

            self._is_cancelled = False
            self._ensure_voice(pipeline, voice)
            generator = pipeline(text, voice=voice, speed=rate)
            sample_rate = 24000

            for result in generator:
                if self._is_cancelled:
                    logger.info("KOKORO: Stream generation cancelled")
                    break
                gs, ps, audio = result
                if audio is not None:
                    if hasattr(audio, 'sr'):
                        sample_rate = audio.sr
                    
                    # Ensure float32 array
                    audio = np.ascontiguousarray(audio, dtype=np.float32)
                    
                    # Apply volume
                    if volume != 1.0:
                        audio = audio * volume

                    yield SynthesisResult(
                        audio_data=audio, # raw numpy array
                        sample_rate=sample_rate,
                        format="raw",
                        provider_name=self.name,
                    )
        except Exception as e:
            logger.error("KOKORO: Streaming synthesis failed: %s", e)
            yield SynthesisResult(
                error=f"Kokoro streaming synthesis failed: {e}",
                provider_name=self.name,
            )

    def speak_blocking(self, text: str, voice_id: Optional[str] = None,
                       rate: float = 1.0, volume: float = 1.0) -> None:
        """Synthesize and play through sounddevice or fallback."""
        result = self.synthesize(text, voice_id, rate, volume)

        if not result.success:
            raise TTSProviderError(result.error or "Kokoro synthesis failed")

        self._play_wav_blocking(result.audio_data, result.sample_rate)

    def stop(self) -> None:
        logger.info("KOKORO: Stop requested")
        # Kokoro doesn't have a persistent engine to stop.
        # Interruption is handled at the router/chunking level.

    def available_voices(self) -> list[VoiceInfo]:
        """List Kokoro's built-in voices, preferring Portuguese then English fallbacks."""
        return [
            # Portuguese Voices (Primary)
            VoiceInfo("pf_dora", "Dora (Female PT-BR)", "pt-BR", "female",
                      "Natural Brazilian Portuguese female voice", ["serene", "default"]),
            VoiceInfo("pm_alex", "Alex (Male PT-BR)", "pt-BR", "male",
                      "Clear Brazilian Portuguese male voice", ["serene", "technical"]),
            VoiceInfo("pm_santa", "Santa (Male PT-BR)", "pt-BR", "male",
                      "Warm, expressive Brazilian Portuguese male voice", ["didactic", "expressive"]),
            
            # English Voices (Fallback / Secondary)
            VoiceInfo("af_heart", "Heart (Female)", "en-US", "female",
                      "Warm, natural female voice", ["serene"]),
            VoiceInfo("af_bella", "Bella (Female)", "en-US", "female",
                      "Clear, articulate female voice", ["didactic"]),
            VoiceInfo("am_michael", "Michael (Male)", "en-US", "male",
                      "Calm, steady male voice", ["serene", "technical"]),
            VoiceInfo("af_nicole", "Nicole (Female)", "en-US", "female",
                      "Smooth, professional female voice", ["serene"]),
            VoiceInfo("am_adam", "Adam (Male)", "en-US", "male",
                      "Deep, authoritative male voice", ["technical"]),
        ]

    def set_default_voice(self, voice_id: str) -> None:
        self._default_voice_id = voice_id

    @property
    def is_ready(self) -> bool:
        return self._is_ready

    @property
    def warmup_started_at(self) -> Optional[float]:
        return self._warmup_started_at

    @property
    def warmup_finished_at(self) -> Optional[float]:
        return self._warmup_finished_at

    @property
    def last_warmup_error(self) -> Optional[str]:
        return self._last_warmup_error

    @property
    def pipeline_cache_state(self) -> str:
        return self._pipeline_cache_state

    @property
    def model_cache_hit(self) -> bool:
        return self._model_cache_hit

    @property
    def model_cache_miss(self) -> bool:
        return self._model_cache_miss

    def shutdown(self) -> None:
        self._pipelines.clear()
        logger.info("KOKORO: Shutdown complete")

    # ── Internal Helpers ──────────────────────────────────────────────

    @staticmethod
    def _samples_to_wav(samples, sample_rate: int) -> bytes:
        """Convert float samples to WAV bytes using fast numpy vectorization."""
        import struct
        import numpy as np
        import time

        t0 = time.time()
        
        # Convert to numpy array if it isn't one already
        if not isinstance(samples, np.ndarray):
            samples = np.array(samples, dtype=np.float32)
        else:
            samples = samples.astype(np.float32)

        # Vectorized clamp and scaling to 16-bit signed integer
        clamped = np.clip(samples, -1.0, 1.0)
        pcm_data = (clamped * 32767.0).astype('<i2').tobytes()

        # Build WAV header
        data_size = len(pcm_data)
        header = struct.pack(
            "<4sI4s4sIHHIIHH4sI",
            b"RIFF",
            36 + data_size,
            b"WAVE",
            b"fmt ",
            16,        # chunk size
            1,         # PCM format
            1,         # mono
            sample_rate,
            sample_rate * 2,  # byte rate
            2,         # block align
            16,        # bits per sample
            b"data",
            data_size,
        )

        conversion_ms = (time.time() - t0) * 1000.0
        logger.info("KOKORO_CONVERSION_MS: %.2f ms (vectorized)", conversion_ms)

        return header + pcm_data

    @staticmethod
    def _play_wav_blocking(wav_data, sample_rate: int) -> None:
        """Play WAV bytes or numpy array using sounddevice or wave+pyaudio fallback."""
        try:
            import sounddevice as sd
            import numpy as np
            if isinstance(wav_data, np.ndarray):
                pcm = wav_data.astype(np.float32)
            else:
                # Skip WAV header (44 bytes) and read PCM data
                pcm = np.frombuffer(wav_data[44:], dtype=np.int16).astype(np.float32) / 32767.0
            sd.play(pcm, samplerate=sample_rate)
            sd.wait()
            return
        except ImportError:
            pass

        # Fallback: write to temp file and use platform player
        import tempfile
        import os
        try:
            with tempfile.NamedTemporaryFile(suffix=".wav", delete=False) as f:
                if isinstance(wav_data, np.ndarray):
                    f.write(KokoroProvider._samples_to_wav(wav_data, sample_rate))
                else:
                    f.write(wav_data)
                tmp_path = f.name

            if os.name == 'nt':
                import winsound
                winsound.PlaySound(tmp_path, winsound.SND_FILENAME)
            else:
                os.system(f'aplay "{tmp_path}" 2>/dev/null || afplay "{tmp_path}" 2>/dev/null')
        finally:
            try:
                os.unlink(tmp_path)
            except Exception:
                pass
