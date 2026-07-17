"""Testes de pausa/retomada da narração (retomada no mesmo ponto).

Cobre as três camadas: ContinuousAudioPlayer (pausa NÃO-BLOQUEANTE por flag —
o callback emite silêncio, sem Pa_StopStream, para não congelar a GUI: item D),
TTSRouter (delegação ao player ativo) e AudioWorker (delegação ao router).
"""
from unittest.mock import MagicMock

from src.core.audio.continuous_player import ContinuousAudioPlayer
from src.core.tts.tts_router import TTSRouter


# ── ContinuousAudioPlayer ────────────────────────────────────────────

def test_player_pause_is_nonblocking_and_keeps_stream_open():
    """Item D: pause() NÃO chama stream.stop()/close() (Pa_StopStream bloqueia
    a thread da GUI). Só sinaliza _is_paused; o stream continua aberto."""
    player = ContinuousAudioPlayer()
    player._stream = MagicMock()
    player._is_playing = True
    player._is_paused = False

    player.pause()

    player._stream.stop.assert_not_called()
    player._stream.close.assert_not_called()
    assert player._is_paused is True


def test_player_resume_is_nonblocking():
    """resume() só limpa o flag — sem stream.start() (o stream nunca parou)."""
    player = ContinuousAudioPlayer()
    player._stream = MagicMock()
    player._is_playing = True
    player._is_paused = True

    player.resume()

    player._stream.start.assert_not_called()
    assert player._is_paused is False


def test_player_pause_is_idempotent():
    player = ContinuousAudioPlayer()
    player._stream = MagicMock()
    player._is_playing = True
    player._is_paused = True  # já pausado

    player.pause()

    player._stream.stop.assert_not_called()


def test_player_stop_clears_paused_flag():
    player = ContinuousAudioPlayer()
    player._stream = MagicMock()
    player._is_playing = True
    player._is_paused = True

    player.stop()

    assert player._is_paused is False
    assert player._is_playing is False


# ── TTSRouter ────────────────────────────────────────────────────────

def test_router_pause_delegates_to_player():
    router = TTSRouter()
    router._active_player = MagicMock()
    router.pause()
    router._active_player.pause.assert_called_once()


def test_router_resume_delegates_to_player():
    router = TTSRouter()
    router._active_player = MagicMock()
    router.resume()
    router._active_player.resume.assert_called_once()


def test_router_pause_resume_without_player_is_safe():
    router = TTSRouter()
    router.pause()   # _active_player é None — não deve levantar
    router.resume()


# ── AudioWorker ──────────────────────────────────────────────────────

def test_worker_pause_resume_delegate_to_router():
    from src.gui.workers.audio_worker import AudioWorker

    fake_router = MagicMock()
    worker = AudioWorker("um texto qualquer", router=fake_router, parent=None)

    worker.pause()
    fake_router.pause.assert_called_once()

    worker.resume()
    fake_router.resume.assert_called_once()
