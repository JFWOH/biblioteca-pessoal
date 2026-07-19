"""Rodada 4 (perf/gui) — parada ASSÍNCRONA da narração.

``ReaderView._stop_audio_if_running`` não pode mais bloquear a GUI (antes:
``wait(2000)``). O worker é apenas SINALIZADO para parar e movido para
``_retiring_workers``; sua referência só é solta quando o ``finished`` REAL
chega (nunca destruímos um QThread cuja thread do SO ainda vive — lição do
PR #32). Uma narração NOVA pedida enquanto o antigo drena é ENFILEIRADA e só
dispara no ``finished`` do antigo (o TTSRouter é compartilhado e não tolera
dois ``speak()`` simultâneos).

Como o ReaderView completo não instancia na suíte (QtWebEngine), montamos um
harness com os métodos REAIS ligados (mesmo padrão de
``test_index_narration_gating``) e stubamos só os colaboradores de UI/QTimer.
"""
from unittest.mock import MagicMock

from src.gui.reader_view import ReaderView


class _StopHarness:
    # Métodos REAIS sob teste (unbound → chamados com self=harness).
    _stop_audio_if_running = ReaderView._stop_audio_if_running
    _retire_current_audio_worker = ReaderView._retire_current_audio_worker
    _on_retiring_worker_finished = ReaderView._on_retiring_worker_finished
    _start_or_defer_narration = ReaderView._start_or_defer_narration
    _run_pending_narration = ReaderView._run_pending_narration
    _teardown_audio_workers = ReaderView._teardown_audio_workers
    _on_pending_safety_timeout = ReaderView._on_pending_safety_timeout
    _audio_worker_signal_pairs = ReaderView._audio_worker_signal_pairs
    _disconnect_audio_worker_signals = ReaderView._disconnect_audio_worker_signals

    def __init__(self):
        self._audio_worker = None
        self._retiring_workers = []
        self._pending_narration = None
        self._pending_narration_timer = None
        self._audio_stopped_by_user = False
        self._audio_paused = False
        self._act_audio_stop = MagicMock()
        self.status_messages = []
        # Handlers de UI referenciados por _audio_worker_signal_pairs (a fonte
        # única A6) — stubs inertes; o harness não tem UI.
        self._on_audio_started = lambda *a: None
        self._on_audio_finished = lambda *a: None
        self._on_audio_error = lambda *a: None
        self._on_audio_worker_finished = lambda *a: None
        self._on_audio_provider_changed = lambda *a: None

    # Colaboradores stubados (QTimer/QApplication não são necessários aqui).
    def _invalidate_presynth(self):
        pass

    def _arm_pending_safety_timer(self):
        self._pending_narration_timer = "armed"

    def _cancel_pending_safety_timer(self):
        self._pending_narration_timer = None

    def _set_audio_button_state(self, *a, **k):
        pass

    def _show_status(self, msg, ms=4000):
        self.status_messages.append(msg)


def _fake_worker(running=True):
    w = MagicMock()
    w.isRunning.return_value = running
    return w


# ── Parada não-bloqueante ────────────────────────────────────────────────────

def test_stop_is_nonblocking_and_retires_running_worker():
    h = _StopHarness()
    w = _fake_worker(running=True)
    h._audio_worker = w

    h._stop_audio_if_running()

    assert h._audio_worker is None          # some do estado "atual"
    assert w in h._retiring_workers         # mas segue vivo, drenando
    w.stop.assert_called_once()             # stop cooperativo
    w.wait.assert_not_called()              # NUNCA bloqueia a GUI
    assert h._audio_stopped_by_user is True
    # Desconectou os callbacks de UI do worker antigo (não devem mais agir).
    w.playback_finished.disconnect.assert_called()
    w.provider_changed.disconnect.assert_called()
    # E reconectou finished ao handler de aposentadoria.
    w.finished.connect.assert_called()


def test_stop_without_worker_is_safe():
    h = _StopHarness()
    h._stop_audio_if_running()
    assert h._audio_worker is None
    assert h._retiring_workers == []


def test_stop_of_already_finished_worker_is_released_not_retired():
    h = _StopHarness()
    w = _fake_worker(running=False)  # já terminou
    h._audio_worker = w

    h._stop_audio_if_running()

    assert w not in h._retiring_workers
    w.deleteLater.assert_called_once()
    w.stop.assert_not_called()

    # Auditoria C: limpeza imediata ⇒ a PRÓXIMA narração NÃO é adiada.
    h._audio_stopped_by_user = False
    launched = []
    h._start_or_defer_narration(lambda: launched.append("go"))
    assert launched == ["go"]


def test_retire_covers_lost_finished_race():
    """Auditoria A2: run() retorna ENTRE o isRunning() e o finished.connect —
    o sinal é emitido sem receptor. O re-check pós-connect trata direto
    (handler idempotente) e o worker NÃO fica preso em _retiring_workers
    (senão toda narração seguinte esperaria o watchdog pela sessão inteira)."""
    h = _StopHarness()
    w = MagicMock()
    w.isRunning.side_effect = [True, False]  # vivo no 1º check; morto no re-check
    h._audio_worker = w

    h._retire_current_audio_worker()

    assert h._retiring_workers == []
    w.deleteLater.assert_called_once()

    # E a próxima narração sai NA HORA, sem deferral nem watchdog.
    launched = []
    h._start_or_defer_narration(lambda: launched.append("go"))
    assert launched == ["go"]


def test_retiring_finished_handler_is_idempotent():
    """Auditoria A2: o handler pode ser chamado pelo finished queued E pelo
    re-check direto — a segunda chamada deve ser no-op."""
    h = _StopHarness()
    w = _fake_worker(running=False)
    h._retiring_workers = [w]

    h._on_retiring_worker_finished(w)
    h._on_retiring_worker_finished(w)  # segunda chamada: worker já fora da lista

    assert h._retiring_workers == []
    w.deleteLater.assert_called_once()


# ── Serialização da narração nova sobre o TTSRouter compartilhado ────────────

def test_start_runs_immediately_when_nothing_retiring():
    h = _StopHarness()
    launched = []
    h._start_or_defer_narration(lambda: launched.append("go"))
    assert launched == ["go"]


def test_new_narration_is_deferred_while_old_drains_then_fires_on_finished():
    h = _StopHarness()
    w = _fake_worker(running=True)
    h._audio_worker = w
    h._stop_audio_if_running()          # w vai para _retiring_workers

    # Uma narração NOVA é pedida enquanto w drena (o _launch_audio_worker real
    # zera _audio_stopped_by_user antes de enfileirar).
    h._audio_stopped_by_user = False
    launched = []
    h._start_or_defer_narration(lambda: launched.append("go"))

    assert launched == []               # ENFILEIRADA, não disparou já
    assert h._pending_narration is not None
    assert h._pending_narration_timer == "armed"

    # w termina de fato (finished real) → a narração enfileirada dispara.
    h._on_retiring_worker_finished(w)

    assert launched == ["go"]
    assert h._pending_narration is None
    assert w not in h._retiring_workers
    w.deleteLater.assert_called()


def test_stop_cancels_a_pending_narration():
    h = _StopHarness()
    h._retiring_workers = [_fake_worker(running=True)]
    h._start_or_defer_narration(lambda: None)
    assert h._pending_narration is not None

    # Usuário para de vez: a narração enfileirada é descartada.
    h._audio_worker = None
    h._stop_audio_if_running()
    assert h._pending_narration is None


def test_run_pending_is_skipped_when_user_stopped():
    h = _StopHarness()
    h._audio_stopped_by_user = True
    launched = []
    h._pending_narration = lambda: launched.append("go")
    h._run_pending_narration()
    assert launched == []  # parar de vez não ressuscita a narração


def test_run_pending_is_skipped_when_something_already_playing():
    h = _StopHarness()
    h._audio_worker = _fake_worker(running=True)  # já toca
    launched = []
    h._pending_narration = lambda: launched.append("go")
    h._run_pending_narration()
    assert launched == []  # não empilha um segundo player


# ── Watchdog (auditoria A3): jamais lança speak() com worker antigo vivo ────

def test_watchdog_never_launches_while_old_worker_alive():
    """Timeout com worker VIVO: não lança (o TTSRouter compartilhado não
    tolera dois speak() — o novo des-cancelaria o antigo e clobberaria
    _active_player), re-emite o stop, avisa na statusbar e RE-ARMA o timer.
    O pending só dispara no finished real."""
    h = _StopHarness()
    w = _fake_worker(running=True)
    h._retiring_workers = [w]
    launched = []
    h._pending_narration = lambda: launched.append("go")

    h._on_pending_safety_timeout()

    assert launched == []                          # NUNCA com worker vivo
    assert h._pending_narration is not None        # pending preservado
    assert h._pending_narration_timer == "armed"   # re-armado
    w.stop.assert_called()                         # stop re-emitido (idempotente)
    assert h.status_messages                       # feedback único na statusbar
    assert w in h._retiring_workers                # referência mantida

    # O finished REAL chega → agora sim o pending dispara.
    h._on_retiring_worker_finished(w)
    assert launched == ["go"]
    assert h._retiring_workers == []


def test_watchdog_purges_finished_workers_and_launches_pending():
    """Timeout com worker que JÁ terminou (finished perdido): purga via o
    handler idempotente — que, ao esvaziar a lista, dispara o pending."""
    h = _StopHarness()
    w = _fake_worker(running=False)
    h._retiring_workers = [w]
    launched = []
    h._pending_narration = lambda: launched.append("go")

    h._on_pending_safety_timeout()

    assert launched == ["go"]
    assert h._retiring_workers == []
    w.deleteLater.assert_called_once()
    assert h._pending_narration_timer is None      # nada para re-armar


# ── Teardown (fechar leitor) — aqui um wait bloqueante É aceitável ──────────

def test_teardown_waits_all_workers_and_clears():
    h = _StopHarness()
    current = _fake_worker(running=True)
    retiring = _fake_worker(running=True)
    # isRunning: True (entra no stop/wait) → False (thread encerrou no wait).
    current.isRunning.side_effect = [True, False]
    retiring.isRunning.side_effect = [True, False]
    h._audio_worker = current
    h._retiring_workers = [retiring]

    h._teardown_audio_workers()

    assert h._audio_worker is None
    assert h._retiring_workers == []
    current.wait.assert_called_once()   # teardown PODE bloquear (encerramento)
    retiring.wait.assert_called_once()
    current.deleteLater.assert_called()
    retiring.deleteLater.assert_called()
    assert h._audio_stopped_by_user is True


def test_teardown_never_deletes_worker_with_live_thread():
    """Auditoria A4: wait(2000) EXPIROU e a thread do SO segue viva —
    deleteLater aqui é a classe exata do SIGABRT do PR #32. A referência é
    abandonada deliberadamente (vazamento consciente no teardown)."""
    h = _StopHarness()
    w = _fake_worker(running=True)  # isRunning SEMPRE True: o wait expirou
    h._audio_worker = w

    h._teardown_audio_workers()

    w.wait.assert_called_once()
    w.deleteLater.assert_not_called()   # NUNCA destruir QThread com thread viva
    assert h._audio_worker is None
    assert h._retiring_workers == []


# ── AudioWorker.run(): cancel checado antes do speak (auditoria A1) ─────────

def test_audio_worker_checks_cancel_before_speak(qtbot):
    """Worker aposentado ANTES de o run() chegar ao speak() não pode narrar:
    router.speak() reseta _is_cancelled do ROUTER na entrada e apagaria o
    próprio stop — a página inteira tocaria em background."""
    from src.gui.workers.audio_worker import AudioWorker

    router = MagicMock()
    router.get_active_provider_name.return_value = "kokoro"
    w = AudioWorker("um texto qualquer", router=router, parent=None)

    w.stop()   # aposentadoria: cancela antes de a thread rodar
    w.run()    # corpo executado diretamente (sem thread)

    router.speak.assert_not_called()


def test_audio_worker_speaks_when_not_cancelled(qtbot):
    """Controle positivo: sem cancelamento, o run() chega ao speak()."""
    from src.gui.workers.audio_worker import AudioWorker

    router = MagicMock()
    router.get_active_provider_name.return_value = "kokoro"
    router.speak.return_value = 3
    w = AudioWorker("um texto qualquer", router=router, parent=None)

    finished = []
    w.playback_finished.connect(finished.append)
    w.run()

    router.speak.assert_called_once()
    assert finished == [3]
