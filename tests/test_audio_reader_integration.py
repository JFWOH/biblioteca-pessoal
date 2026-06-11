"""
Integration tests for Phase 13A TTS runtime and Audio Player optimization.
"""

import pytest
import numpy as np
import time
from unittest.mock import MagicMock, patch

from src.core.tts.tts_router import TTSRouter
from src.core.tts.kokoro_provider import KokoroProvider
from src.core.tts.piper_provider import PiperProvider
from src.core.audio.continuous_player import ContinuousAudioPlayer
from src.core.tts.voice_profile import VoiceProfile, NarrationRole

try:
    import kokoro
    HAS_KOKORO = True
except ImportError:
    HAS_KOKORO = False

try:
    import piper
    HAS_PIPER = True
except ImportError:
    HAS_PIPER = False



class TestTTSIntegrationOptimizations:

    def test_vectorized_wav_conversion_correctness(self):
        """Test that the vectorized numpy conversion matches format expectations and is fast."""
        samples = np.random.uniform(-1.0, 1.0, 24000).astype(np.float32)
        
        t0 = time.time()
        wav_data = KokoroProvider._samples_to_wav(samples, 24000)
        duration_ms = (time.time() - t0) * 1000.0
        
        # Verify it runs in less than 20ms (usually < 1ms)
        assert duration_ms < 20.0
        
        # Verify WAV header structure
        assert wav_data.startswith(b"RIFF")
        assert b"WAVE" in wav_data[:12]
        assert len(wav_data) == 44 + len(samples) * 2

    def test_continuous_player_accepts_numpy_array(self):
        """Test that the continuous player enqueues numpy arrays without crashing."""
        player = ContinuousAudioPlayer(sample_rate=24000)
        player._available = True  # Mock availability
        player._is_playing = True
        
        # Enqueue raw numpy float32 samples
        samples = np.zeros(12000, dtype=np.float32)
        
        with patch.object(player._queue, 'put') as mock_put:
            player.enqueue(samples, sample_rate=24000, channels=1, dtype='float32')
            assert mock_put.called
            args, _ = mock_put.call_args
            pcm_enqueued, sr_enqueued = args[0]
            assert isinstance(pcm_enqueued, np.ndarray)
            assert sr_enqueued == player._sample_rate

    @pytest.mark.skipif(not HAS_PIPER, reason="piper library not installed")
    def test_piper_model_cache_reused(self):
        """Test that PiperProvider caches and reuses the loaded voice model."""
        provider = PiperProvider()
        provider._available = True
        provider._model_path = "dummy_model.onnx"
        
        mock_voice = MagicMock()
        
        with patch("piper.PiperVoice.load", return_value=mock_voice) as mock_load, \
             patch("wave.open"), \
             patch("io.BytesIO"):
            
            # First synthesis should load the model
            provider._synthesize_python("Olá mundo", voice_id="pt_BR-faber-medium", rate=1.0, volume=1.0)
            assert mock_load.call_count == 1
            
            # Second synthesis should reuse the model from cache
            provider._synthesize_python("Olá novamente", voice_id="pt_BR-faber-medium", rate=1.0, volume=1.0)
            assert mock_load.call_count == 1

    @pytest.mark.skipif(not (HAS_KOKORO and HAS_PIPER), reason="kokoro and/or piper library not installed")
    def test_provider_format_metadata(self):
        """Test that Kokoro and Piper providers expose format properties correctly."""
        kokoro = KokoroProvider()
        piper = PiperProvider()
        
        assert kokoro.sample_rate == 24000
        assert kokoro.dtype == 'float32'
        assert kokoro.channels == 1
        
        assert piper.sample_rate == 22050
        assert piper.dtype == 'int16'
        assert piper.channels == 1

    @pytest.mark.skipif(not HAS_KOKORO, reason="kokoro library not installed")
    def test_kokoro_streaming_generator(self):
        """Test that KokoroProvider's synthesize_stream yields segments correctly."""
        provider = KokoroProvider()
        provider._available = True
        provider._is_ready = True
        
        mock_pipeline = MagicMock()
        # Mock generator returning a single segment
        mock_pipeline.return_value = [("g", "p", np.zeros(1000, dtype=np.float32))]
        
        with patch.object(provider, "_get_pipeline", return_value=mock_pipeline):
            stream = provider.synthesize_stream("Texto teste")
            results = list(stream)
            
            assert len(results) == 1
            assert results[0].success
            assert results[0].format == "raw"
            assert isinstance(results[0].audio_data, np.ndarray)
