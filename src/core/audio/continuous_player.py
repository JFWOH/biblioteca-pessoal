"""
Continuous Audio Player for gapless TTS playback.

Uses sounddevice OutputStream to provide a continuous, thread-safe
audio playback buffer, preventing the audio gaps that occur with blocking synthesis.
"""
import logging
import queue
import time
import os

logger = logging.getLogger(__name__)

class ContinuousAudioPlayer:
    def __init__(self, sample_rate: int = 24000, channels: int = 1, fade_ms: int = 20):
        self._sample_rate = sample_rate
        self._channels = channels
        self._fade_ms = fade_ms
        self._is_playing = False
        self._is_paused = False
        self._queue = queue.Queue(maxsize=10)
        self._stream = None
        self._buffer = None
        
        self._available = False
        try:
            import sounddevice as sd  # noqa: F401 — só testa disponibilidade aqui
            import numpy as np
            self._available = True
            self._buffer = np.zeros(0, dtype=np.float32)
        except ImportError:
            logger.warning("sounddevice or numpy not available. Continuous playback will fall back to blocking.")

    def start(self):
        if not self._available:
            logger.warning("PLAYER_STREAM_OPENED_FAILED: Player not available.")
            return
            
        import sounddevice as sd
        import numpy as np
        self._is_playing = True
        self._is_paused = False
        self._buffer = np.zeros(0, dtype=np.float32)
        
        # Clear queue
        while not self._queue.empty():
            try:
                self._queue.get_nowait()
            except queue.Empty:
                break
                
        try:
            # Detect native sample rate of the default output device
            try:
                default_device_id = sd.default.device[1]
                if default_device_id >= 0:
                    device_info = sd.query_devices(default_device_id, 'output')
                    self._sample_rate = int(device_info.get('default_samplerate', 44100))
                    logger.info("PLAYER_NATIVE_RATE_DETECTED: %d Hz", self._sample_rate)
                else:
                    self._sample_rate = 44100
            except Exception as e:
                logger.warning("PLAYER_DEVICE_QUERY_FAILED: Using fallback 44100 Hz: %s", e)
                self._sample_rate = 44100

            logger.info("PLAYER_STREAM_OPENING: sample_rate=%d, channels=2", self._sample_rate)
            self._stream = sd.OutputStream(
                samplerate=self._sample_rate,
                channels=2,
                dtype='float32',
                callback=self._audio_callback,
            )
            self._stream.start()
            logger.info("PLAYER_STREAM_OPENED: device=%s, sample_rate=%d, channels=2", 
                        self._stream.device, self._sample_rate)
            logger.info("PLAYER_DEVICE: %s", self._stream.device)
            logger.info("PLAYER_SAMPLERATE: %d", self._sample_rate)
            logger.info("PLAYER_DTYPE: float32")
            logger.info("PLAYER_CHANNELS: 2")
        except Exception as e:
            logger.error("PLAYER_STREAM_OPENED_FAILED: Failed to start OutputStream: %s", e)
            self._available = False

    def _audio_callback(self, outdata, frames, time_info, status):
        """Callback for sounddevice. Called in a separate C thread."""
        import numpy as np
        
        if status:
            logger.debug("PLAYER_UNDERFLOW: OutputStream status warning: %s", status)

        # If buffer is too small, try to get more data from queue
        while len(self._buffer) < frames and not self._queue.empty():
            try:
                pcm, sr = self._queue.get_nowait()
                logger.debug("PLAYER_CALLBACK_CONSUMED: Got pcm chunk from queue. length=%d, sr=%d", len(pcm), sr)
                self._buffer = np.concatenate((self._buffer, pcm))
            except queue.Empty:
                break
                
        # Fill outdata (always stereo)
        if len(self._buffer) == 0:
            logger.debug("PLAYER_OUTPUT_ZEROED: No data in buffer, filling with zero.")
            outdata.fill(0)
        elif len(self._buffer) >= frames:
            data = self._buffer[:frames]
            outdata[:, 0] = data
            outdata[:, 1] = data
            self._buffer = self._buffer[frames:]
        else:
            logger.debug("PLAYER_OUTPUT_ZEROED_PARTIAL: Buffer has %d frames, needed %d. Filling rest with zeros.", len(self._buffer), frames)
            data = self._buffer
            outdata[:len(data), 0] = data
            outdata[:len(data), 1] = data
            outdata[len(data):].fill(0)
            self._buffer = np.zeros(0, dtype=np.float32)

    def enqueue(self, audio, sample_rate: int, channels: int = 1, dtype: str = 'float32'):
        """Enqueue raw audio (np.ndarray) or WAV bytes to the continuous player."""
        logger.info("CHUNK_SAMPLERATE: %d", sample_rate)
        logger.info("CHUNK_DTYPE: %s", dtype)
        logger.info("CHUNK_CHANNELS: %d", channels)

        if not self._available:
            logger.info("PLAYER_FALLBACK_BLOCKING: Using blocking fallback play.")
            self._play_wav_blocking(audio, sample_rate)
            return

        import numpy as np
        try:
            if isinstance(audio, bytes):
                # If it's bytes, it could be WAV bytes or raw PCM bytes
                if audio.startswith(b"RIFF") and b"WAVE" in audio[:12]:
                    # WAV bytes: read metadata from header (assumed mono int16 for Kokoro/Piper)
                    pcm = np.frombuffer(audio[44:], dtype=np.int16).astype(np.float32) / 32767.0
                else:
                    # Raw PCM bytes: convert according to dtype parameter
                    if dtype == 'int16':
                        pcm = np.frombuffer(audio, dtype=np.int16).astype(np.float32) / 32767.0
                    else:
                        pcm = np.frombuffer(audio, dtype=np.float32)
            elif isinstance(audio, np.ndarray):
                # np.ndarray: convert according to its dtype
                if np.issubdtype(audio.dtype, np.integer):
                    pcm = audio.astype(np.float32) / 32767.0
                else:
                    pcm = audio.astype(np.float32)
            else:
                # List of float samples
                pcm = np.array(audio, dtype=np.float32)

            # Map multi-channel input to mono by averaging channels
            if channels > 1:
                pcm = pcm.reshape(-1, channels).mean(axis=1)

            # Resample to native player sample rate if there is a mismatch
            if sample_rate != self._sample_rate:
                logger.info("PLAYER_RESAMPLING: from %d Hz to %d Hz", sample_rate, self._sample_rate)
                duration = len(pcm) / sample_rate
                old_indices = np.arange(len(pcm))
                new_indices = np.linspace(0, len(pcm) - 1, int(duration * self._sample_rate))
                pcm = np.interp(new_indices, old_indices, pcm).astype(np.float32)

            logger.info("CHUNK_DECODED: frames=%d, dtype=float32", len(pcm))
        except Exception as e:
            logger.error("CHUNK_DECODE_FAILED: Error processing audio data: %s", e)
            return
            
        while self._is_playing:
            try:
                self._queue.put((pcm, self._sample_rate), timeout=0.1)
                logger.info("CHUNK_0_ENQUEUED: queue_size=%d", self._queue.qsize())
                break
            except queue.Full:
                logger.warning("PLAYER_QUEUE_FULL: Retrying enqueue...")
                continue

    def pause(self):
        """Pausa a reprodução preservando buffer e fila (retomada no mesmo ponto).

        Usa ``stream.stop()`` (sem ``close()``): o PortAudio para de chamar o
        callback, mas o estado do stream e os dados já bufferizados permanecem,
        então ``resume()`` continua exatamente de onde parou.
        """
        if self._stream is not None and self._is_playing and not self._is_paused:
            try:
                self._stream.stop()
                self._is_paused = True
                logger.info("PLAYER_PAUSED: playback paused.")
            except Exception as e:
                logger.error("PLAYER_PAUSE_ERROR: %s", e)

    def resume(self):
        """Retoma a reprodução pausada a partir do ponto exato."""
        if self._stream is not None and self._is_paused:
            try:
                self._stream.start()
                self._is_paused = False
                logger.info("PLAYER_RESUMED: playback resumed.")
            except Exception as e:
                logger.error("PLAYER_RESUME_ERROR: %s", e)

    def stop(self):
        logger.info("PLAYER_STOPPED: stop requested.")
        self._is_playing = False
        self._is_paused = False
        if self._stream is not None:
            try:
                self._stream.stop()
                self._stream.close()
            except Exception as e:
                logger.error("PLAYER_STREAM_STOP_ERROR: %s", e)
            self._stream = None
            
        while not self._queue.empty():
            try:
                self._queue.get_nowait()
            except queue.Empty:
                break

    @staticmethod
    def _play_wav_blocking(wav_data, sample_rate: int) -> None:
        """Fallback blocking play."""
        try:
            import sounddevice as sd
            import numpy as np
            if isinstance(wav_data, np.ndarray):
                pcm = wav_data.astype(np.float32)
            else:
                pcm = np.frombuffer(wav_data[44:], dtype=np.int16).astype(np.float32) / 32767.0
            logger.info("BLOCKING_PLAY_START: sample_rate=%d, frames=%d", sample_rate, len(pcm))
            sd.play(pcm, samplerate=sample_rate)
            sd.wait()
            logger.info("BLOCKING_PLAY_FINISHED")
            return
        except ImportError:
            pass

        import tempfile
        try:
            with tempfile.NamedTemporaryFile(suffix=".wav", delete=False) as f:
                if isinstance(wav_data, np.ndarray):
                    from src.core.tts.kokoro_provider import KokoroProvider
                    f.write(KokoroProvider._samples_to_wav(wav_data, sample_rate))
                else:
                    f.write(wav_data)
                tmp_path = f.name
            if os.name == 'nt':
                import winsound
                logger.info("BLOCKING_PLAY_WINSOUND: playing %s", tmp_path)
                winsound.PlaySound(tmp_path, winsound.SND_FILENAME)
            else:
                logger.info("BLOCKING_PLAY_OS: playing %s", tmp_path)
                os.system(f'aplay "{tmp_path}" 2>/dev/null || afplay "{tmp_path}" 2>/dev/null')
        finally:
            try:
                os.unlink(tmp_path)
            except Exception:
                pass

    def wait_until_done(self):
        """Blocks until the queue is empty and buffer is played."""
        if not self._available:
            return

        while not self._queue.empty() and self._is_playing:
            time.sleep(0.1)

        while self._buffer is not None and len(self._buffer) > 0 and self._is_playing:
            time.sleep(0.1)

        time.sleep(0.1)


class PreSynthesisCache:
    """Cache de UMA página de áudio pré-sintetizada (tarefa 3.6).

    Estrutura de dados PURA (ADR-006): sem threads, sem GUI, sem I/O de áudio.
    Guarda no máximo UMA entrada (a próxima página à frente) para não estourar
    memória/recursos. Quem sintetiza (worker na GUI) chama ``store``; quem vai
    tocar chama ``take`` com a mesma chave. A chave carrega ``book_id + página +
    assinatura de voz/velocidade`` para que uma troca de livro, de página ou de
    voz descarte automaticamente o áudio obsoleto (invalidação por chave).

    Cada segmento é um dict ``{"audio_data", "sample_rate", "channels",
    "dtype"}`` — o mesmo formato que ``ContinuousAudioPlayer.enqueue`` consome.
    """

    def __init__(self):
        self._key = None
        self._segments: list[dict] | None = None

    def store(self, key, segments: list[dict]) -> None:
        """Guarda os segmentos sob ``key`` (substitui qualquer entrada anterior)."""
        self._key = key
        self._segments = list(segments) if segments else None

    def has(self, key) -> bool:
        """True se há áudio pronto exatamente para ``key``."""
        return self._segments is not None and self._key == key

    @property
    def pending_key(self):
        """Chave atualmente em cache (ou None) — usada para não re-sintetizar."""
        return self._key if self._segments is not None else None

    def take(self, key) -> list[dict] | None:
        """Devolve e REMOVE os segmentos de ``key``; None se não bater a chave."""
        if self.has(key):
            segments = self._segments
            self.invalidate()
            return segments
        return None

    def invalidate(self) -> None:
        """Descarta qualquer áudio em cache (navegação manual / stop / troca)."""
        self._key = None
        self._segments = None
