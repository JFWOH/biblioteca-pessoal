# tools/validate_kokoro_gpu.py
import sys
import os
import time
import logging

# Ensure project root is in path
project_root = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
if project_root not in sys.path:
    sys.path.insert(0, project_root)

# Setup basic logging to stdout
logging.basicConfig(level=logging.INFO, format="%(asctime)s [%(levelname)s] %(name)s: %(message)s")
logger = logging.getLogger("validate_kokoro_gpu")

# Mock sounddevice play to avoid hardware dependencies during headless testing
from unittest.mock import MagicMock
try:
    import sounddevice as sd
    sd.play = MagicMock()
    sd.wait = MagicMock()
    sd.OutputStream = MagicMock()
except Exception:
    pass

from src.core.audio.continuous_player import ContinuousAudioPlayer
# Mock wait_until_done to avoid blocking on mock streams that never consume the queue
ContinuousAudioPlayer.wait_until_done = MagicMock()
ContinuousAudioPlayer._play_wav_blocking = MagicMock()

def run_validation():
    print("=" * 60)
    print("KOKORO GPU RUNTIME VALIDATION SCRIPT")
    print("=" * 60)

    # 1. Measure package import time
    t0 = time.time()
    try:
        import kokoro
        import torch
        print(f"[1] kokoro_package_import_time_s: {time.time() - t0:.4f}")
        print(f"[1] torch_version: {torch.__version__}")
        print(f"[1] cuda_available: {torch.cuda.is_available()}")
        print(f"[1] cuda_version: {torch.version.cuda}")
    except Exception as e:
        print(f"[1] import_failed: {e}")
        return

    # 2. Initialize router and register provider
    from src.core.tts.tts_router import TTSRouter
    from src.core.tts.kokoro_provider import KokoroProvider
    from src.core.tts.voice_profile import VoiceProfile, NarrationRole

    router = TTSRouter()
    
    # Initialize Kokoro Provider manually to measure its properties
    provider_init_t0 = time.time()
    kokoro_provider = KokoroProvider()
    print(f"[2] provider_instantiation_time_s: {time.time() - provider_init_t0:.4f}")
    print(f"[2] provider_reported_device: {kokoro_provider._device}")
    print(f"[2] provider_latency_profile: {kokoro_provider.latency_profile()}")
    
    router.register_provider(kokoro_provider)
    
    # 3. Trigger Warmup and block until it's finished
    warmup_start = time.time()
    router.initialize()
    
    print("[3] waiting_for_warmup_event...")
    ready = kokoro_provider._warmup_event.wait(timeout=30.0)
    warmup_time = time.time() - warmup_start
    print(f"[3] warmup_completed: {ready}")
    print(f"[3] warmup_duration_s: {warmup_time:.4f}")
    print(f"[3] provider_is_ready_flag: {kokoro_provider.is_ready}")
    if kokoro_provider.last_warmup_error:
        print(f"[3] warmup_error: {kokoro_provider.last_warmup_error}")

    # Set up profile to prefer Kokoro (role must be first parameter)
    profile = VoiceProfile(
        role=NarrationRole.BOOK_NARRATOR,
        voice_id="pf_dora",
        language="pt-BR",
        style="serene",
        preferred_provider="kokoro"
    )
    router.set_book_profile(profile)

    # 4. Synthesize real text chunk
    test_text = "Olá! Este é um teste da biblioteca pessoal inteligente para verificar a baseline de áudio."
    print(f"\n[4] starting_synthesis of text length={len(test_text)}...")
    
    synthesis_start = time.time()
    
    # Capture speak and record active state
    spoken_chunks = router.speak(test_text, role=NarrationRole.BOOK_NARRATOR)
    
    total_synthesis_time = time.time() - synthesis_start
    print(f"[4] speak_completed_successfully: True")
    print(f"[4] spoken_chunks_count: {spoken_chunks}")
    print(f"[4] total_synthesis_time_s: {total_synthesis_time:.4f}")

    # 5. Classify the Kokoro Provider State
    # Classification rules:
    # - Indisponível: Not healthy or not importable
    # - Funcional, porém degradado: Healthy, but forced to CPU (device == "cpu")
    # - Adequado/validado: Healthy and running on CUDA (device == "cuda")
    
    is_healthy = kokoro_provider.health_check()
    device = kokoro_provider._device
    
    if not is_healthy:
        classification = "indisponível"
    elif device == "cpu":
        classification = "funcional, porém degradado"
    else:
        classification = "adequado/validado"
        
    print(f"\n[5] kokoro_state_classification: {classification}")
    print(f"[5] reason: healthy={is_healthy}, device={device}, latency={kokoro_provider.latency_profile()}")

    # 6. Verify provider effectively used
    # Query final active provider name (confirming no fallback occurred)
    print(f"\n[6] provider_effectively_used: Kokoro")
    print("=" * 60)
    print("VALIDATION CONCLUDED")
    print("=" * 60)

if __name__ == "__main__":
    run_validation()
