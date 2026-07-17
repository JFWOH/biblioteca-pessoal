"""Item D: pausar a leitura contínua NÃO pode bloquear a thread chamadora.

Causa raiz confirmada: ``ContinuousAudioPlayer.pause()`` chamava
``stream.stop()`` (Pa_StopStream), que bloqueia até o buffer drenar — e pode
travar por muito mais tempo se a pré-síntese estiver segurando o GIL. Como a
pausa parte da thread da GUI, isso congelava a interface. O fix torna a pausa
um simples sinal (o callback emite silêncio), sem qualquer chamada bloqueante.
"""
import threading
import time
from unittest.mock import MagicMock

from src.core.audio.continuous_player import ContinuousAudioPlayer
from src.core.tts.tts_router import TTSRouter


def test_pause_does_not_call_blocking_stream_stop():
    player = ContinuousAudioPlayer()
    player._is_playing = True
    player._is_paused = False
    stream = MagicMock()
    player._stream = stream

    player.pause()

    stream.stop.assert_not_called()   # Pa_StopStream bloquearia a GUI
    stream.abort.assert_not_called()
    assert player._is_paused is True

    player.resume()
    stream.start.assert_not_called()
    assert player._is_paused is False


def test_pause_returns_immediately_even_if_stream_stop_would_block():
    player = ContinuousAudioPlayer()
    player._is_playing = True
    player._is_paused = False
    stream = MagicMock()
    stream.stop.side_effect = lambda: time.sleep(5)  # se fosse chamada, travaria
    player._stream = stream

    t0 = time.perf_counter()
    player.pause()
    elapsed = time.perf_counter() - t0

    assert elapsed < 0.5, "pause() bloqueou a thread chamadora"
    assert player._is_paused is True
    stream.stop.assert_not_called()


def test_paused_callback_outputs_silence_and_preserves_buffer():
    import numpy as np
    player = ContinuousAudioPlayer()
    player._is_paused = True
    player._buffer = np.ones(10, dtype=np.float32)

    outdata = np.ones((5, 2), dtype=np.float32)
    player._audio_callback(outdata, 5, None, None)

    assert np.all(outdata == 0)                       # emitiu silêncio
    assert np.array_equal(player._buffer, np.ones(10, dtype=np.float32))  # buffer intacto


def test_worker_pause_chain_is_nonblocking_while_presynthesis_runs():
    """Simula a pré-síntese ocupada em background e prova que pausar pela
    thread chamadora (GUI) retorna na hora, sem esperar síntese nem stream."""
    from src.gui.workers.audio_worker import AudioWorker

    synth_running = threading.Event()
    release = threading.Event()

    def fake_presynthesis():
        synth_running.set()
        release.wait(2.0)  # "síntese" pesada em andamento

    bg = threading.Thread(target=fake_presynthesis, daemon=True)
    bg.start()
    assert synth_running.wait(1.0)

    player = ContinuousAudioPlayer()
    player._is_playing = True
    player._is_paused = False
    stream = MagicMock()
    stream.stop.side_effect = lambda: time.sleep(5)  # bloquearia se chamada
    player._stream = stream

    router = TTSRouter()
    router._active_player = player
    worker = AudioWorker("um texto qualquer", router=router, parent=None)

    t0 = time.perf_counter()
    worker.pause()  # thread chamadora (simula a GUI)
    elapsed = time.perf_counter() - t0
    release.set()

    assert elapsed < 0.5, "a cadeia GUI→worker→router→player bloqueou ao pausar"
    assert player._is_paused is True
    stream.stop.assert_not_called()
