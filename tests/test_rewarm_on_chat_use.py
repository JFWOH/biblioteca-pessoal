"""Re-warm do modelo ao usar o chat (rodada UX ago/2026, onda Q — cand. N.4).

Sintoma: o warmup roda UMA vez no startup; com o app aberto por horas o
keep_alive do Ollama expira e a primeira pergunta da tarde volta a pagar o
load a frio (5-30s). Correção: abrir o painel do assistente — ou focar o campo
de pergunta — dispara um re-warm em background, com debounce para não
martelar o daemon.

Tudo mockado: nenhum teste aqui fala com o Ollama de verdade.
"""
from unittest.mock import patch

import pytest

from src.core.ollama_defaults import OLLAMA_KEEP_ALIVE
from src.gui.widgets.rag_panel import RAGPanel, REWARM_MIN_INTERVAL_S
from src.gui.workers.warmup_worker import WarmupWorker, spawn_warmup


class _FakeConfig:
    """ConfigManager mínimo (só o .get que o painel usa)."""

    def __init__(self, **valores):
        self._v = valores

    def get(self, key, default=None):
        return self._v.get(key, default)

    def set(self, key, value):
        self._v[key] = value


@pytest.fixture
def painel(qtbot):
    p = RAGPanel()
    qtbot.addWidget(p)
    p.set_config(_FakeConfig(**{
        "rag.ollama_url": "http://localhost:11434",
        "rag.llm_model": "gemma4:12b",
        "rag.embed_model": "bge-m3",
    }))
    return p


def _envelhece(painel, segundos: float) -> None:
    """Finge que o último re-warm foi há `segundos`."""
    painel._last_rewarm_ts -= segundos


# ── Debounce ──────────────────────────────────────────────────────────────

def test_no_rewarm_right_after_startup(painel):
    """O warmup de startup do MainWindow acabou de rodar — não repetir."""
    with patch("src.gui.workers.warmup_worker.spawn_warmup") as spawn:
        assert painel._maybe_rewarm() is False
    spawn.assert_not_called()


def test_rewarm_after_interval(painel):
    _envelhece(painel, REWARM_MIN_INTERVAL_S + 1)
    with patch("src.gui.workers.warmup_worker.spawn_warmup") as spawn:
        assert painel._maybe_rewarm() is True
    spawn.assert_called_once()
    kwargs = spawn.call_args.kwargs
    assert kwargs["llm_model"] == "gemma4:12b"
    assert kwargs["embed_model"] == "bge-m3"
    assert kwargs["ollama_url"] == "http://localhost:11434"


def test_second_rewarm_inside_window_is_debounced(painel):
    _envelhece(painel, REWARM_MIN_INTERVAL_S + 1)
    with patch("src.gui.workers.warmup_worker.spawn_warmup") as spawn:
        assert painel._maybe_rewarm() is True
        # Usuário fecha e reabre o painel várias vezes seguidas.
        assert painel._maybe_rewarm() is False
        assert painel._maybe_rewarm() is False
    assert spawn.call_count == 1


def test_clock_only_advances_when_warmup_actually_started(painel):
    """spawn devolvendo None (worker anterior vivo) não consome a janela."""
    _envelhece(painel, REWARM_MIN_INTERVAL_S + 1)
    with patch("src.gui.workers.warmup_worker.spawn_warmup", return_value=None):
        assert painel._maybe_rewarm() is False
    with patch("src.gui.workers.warmup_worker.spawn_warmup") as spawn:
        assert painel._maybe_rewarm() is True
    spawn.assert_called_once()


def test_no_config_no_rewarm(qtbot):
    """Sem config injetada não há url/modelo — segue em silêncio (ADR-005)."""
    p = RAGPanel()
    qtbot.addWidget(p)
    _envelhece(p, REWARM_MIN_INTERVAL_S + 1)
    with patch("src.gui.workers.warmup_worker.spawn_warmup") as spawn:
        assert p._maybe_rewarm() is False
    spawn.assert_not_called()


def test_rewarm_failure_is_silent(painel):
    """Falha ao disparar vira log debug, nunca exceção na GUI (ADR-005)."""
    _envelhece(painel, REWARM_MIN_INTERVAL_S + 1)
    with patch("src.gui.workers.warmup_worker.spawn_warmup",
               side_effect=RuntimeError("sem thread disponível")):
        assert painel._maybe_rewarm() is False


# ── Gatilhos (abrir o painel / focar o campo) ─────────────────────────────

def test_show_triggers_rewarm(painel):
    """showEvent é entregue de forma síncrona pelo Qt dentro de show()."""
    with patch.object(RAGPanel, "_maybe_rewarm") as tentativa:
        painel.show()
    tentativa.assert_called()
    painel.hide()


def test_focus_on_question_input_triggers_rewarm(painel):
    """Painel já visível há horas: focar o campo é o gatilho que resta."""
    from PyQt6.QtCore import QEvent
    from PyQt6.QtGui import QFocusEvent

    with patch.object(RAGPanel, "_maybe_rewarm") as tentativa:
        painel.eventFilter(painel._question_input,
                           QFocusEvent(QEvent.Type.FocusIn))
    tentativa.assert_called_once()


def test_event_filter_still_handles_escape_in_reason_edit(painel):
    """Regressão: o gatilho novo não pode atrapalhar o Esc dos chips do 👎."""
    from PyQt6.QtCore import QEvent, Qt
    from PyQt6.QtGui import QKeyEvent

    with patch.object(painel, "_cancel_reason_other") as cancel:
        consumiu = painel.eventFilter(
            painel._reason_edit,
            QKeyEvent(QEvent.Type.KeyPress, Qt.Key.Key_Escape,
                      Qt.KeyboardModifier.NoModifier))
    assert consumiu is True
    cancel.assert_called_once()


# ── Reuso seguro do QThread ───────────────────────────────────────────────

class _WorkerFalso:
    def __init__(self, rodando: bool):
        self._rodando = rodando

    def isRunning(self):  # noqa: N802 (assinatura do Qt)
        return self._rodando


def test_spawn_warmup_refuses_to_restart_live_thread():
    """QThread vivo NUNCA é reiniciado: devolve None sem criar/startar nada."""
    with patch("src.gui.workers.warmup_worker.WarmupWorker") as cls:
        assert spawn_warmup(None, llm_model="gemma4:12b",
                            previous=_WorkerFalso(rodando=True)) is None
    cls.assert_not_called()


def test_spawn_warmup_creates_new_instance_when_previous_finished():
    """Worker anterior já terminou → instância NOVA (nunca reuso do objeto)."""
    anterior = _WorkerFalso(rodando=False)
    with patch("src.gui.workers.warmup_worker.WarmupWorker") as cls:
        novo = spawn_warmup(None, ollama_url="http://x:1", llm_model="m",
                            embed_model="e", previous=anterior)
    cls.assert_called_once_with(ollama_url="http://x:1", llm_model="m",
                                embed_model="e", parent=None)
    novo.start.assert_called_once()
    assert novo is not anterior


def test_warmup_worker_keeps_keep_alive_payload():
    """O re-warm reusa o worker de sempre — mesmo payload, mesmo keep_alive."""
    w = WarmupWorker(llm_model="gemma4:12b", embed_model="bge-m3")
    enviados = []
    w._post = lambda endpoint, payload: enviados.append((endpoint, payload))
    w.run()
    assert [e for e, _ in enviados] == ["/api/generate", "/api/embed"]
    assert all(p["keep_alive"] == OLLAMA_KEEP_ALIVE for _, p in enviados)
