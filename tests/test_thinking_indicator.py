"""Observabilidade do raciocínio do RAG.

Cobre as duas metades:
  - núcleo puro: ``_ThinkingStatusTracker`` emite status com CONTAGEM e TEMPO
    ("💭 Pensando… (N tokens · Ns)"), ADR-006 (só strings via callback);
  - GUI: o RAGPanel exibe um indicador PROEMINENTE (objectName
    ``ragThinkingIndicator``) enquanto o modelo pensa/carrega e o esconde
    assim que o conteúdo começa.
"""
from src.core.rag.orchestrator import _ThinkingStatusTracker
from src.gui.widgets.rag_panel import RAGPanel


# ── Núcleo: _ThinkingStatusTracker ────────────────────────────────────────

def test_tracker_emits_count_and_time_with_marker():
    emitted = []
    tracker = _ThinkingStatusTracker(emitted.append)
    tracker.on_chunk({"thinking": "raciocinando..."})
    assert emitted, "deveria emitir status ao receber um chunk de thinking"
    msg = emitted[-1]
    assert msg.startswith("💭"), "marcador 💭 sinaliza raciocínio à GUI"
    assert "1 tokens" in msg
    assert msg.rstrip().endswith("s)"), "deve conter o tempo decorrido"


def test_tracker_counts_multiple_thinking_chunks():
    # O throttle de 1s segura re-emissões; a contagem acumula entre elas e
    # aparece na próxima emissão. Aqui furamos o throttle manualmente (em vez
    # de dormir 1s) para observar a contagem acumulada.
    emitted = []
    tracker = _ThinkingStatusTracker(emitted.append)
    tracker.on_chunk({"thinking": "x"})   # emite "(1 tokens ...)"
    tracker.on_chunk({"thinking": "x"})   # throttled, mas conta
    tracker._last_emit -= 2.0             # simula ~2s decorridos
    tracker.on_chunk({"thinking": "x"})   # emite com a contagem acumulada
    assert tracker._thinking_tokens == 3
    assert "3 tokens" in emitted[-1]


def test_tracker_ignores_content_chunks():
    emitted = []
    tracker = _ThinkingStatusTracker(emitted.append)
    tracker.on_chunk({"content": "olá"})
    assert emitted == []


def test_tracker_no_callback_is_safe():
    # Sem callback (ex.: chamada sem GUI) não deve levantar exceção.
    tracker = _ThinkingStatusTracker(None)
    tracker.on_chunk({"thinking": "x"})
    tracker.on_content_started()


# ── GUI: indicador proeminente do RAGPanel ────────────────────────────────

def test_indicator_hidden_by_default(qtbot):
    panel = RAGPanel()
    qtbot.addWidget(panel)
    assert not panel._thinking_indicator.isVisibleTo(panel)


def test_indicator_shows_on_thinking_status(qtbot):
    panel = RAGPanel()
    qtbot.addWidget(panel)
    panel._set_generating(True)
    panel.on_status_updated("💭 Pensando… (42 tokens · 7s)")
    assert panel._thinking_indicator.isVisibleTo(panel)
    assert panel._thinking_indicator.text() == "💭 Pensando… (42 tokens · 7s)"


def test_indicator_shows_on_model_prep_status(qtbot):
    panel = RAGPanel()
    qtbot.addWidget(panel)
    panel._set_generating(True)
    panel.on_status_updated("🧠 Preparando o modelo… (pode levar ~1 min)")
    assert panel._thinking_indicator.isVisibleTo(panel)


def test_indicator_hidden_on_writing_status(qtbot):
    panel = RAGPanel()
    qtbot.addWidget(panel)
    panel._set_generating(True)
    panel.on_status_updated("💭 Pensando… (10 tokens · 3s)")
    panel.on_status_updated("✍️ Escrevendo resposta…")
    assert not panel._thinking_indicator.isVisibleTo(panel)


def test_indicator_hidden_on_first_content_token(qtbot):
    panel = RAGPanel()
    qtbot.addWidget(panel)
    panel._set_generating(True)
    panel.on_status_updated("💭 Pensando… (10 tokens · 3s)")
    assert panel._thinking_indicator.isVisibleTo(panel)
    panel.on_token_received("A resposta")
    assert not panel._thinking_indicator.isVisibleTo(panel)


def test_indicator_hidden_on_answer_complete(qtbot):
    panel = RAGPanel()
    qtbot.addWidget(panel)
    panel._set_generating(True)
    panel.on_status_updated("💭 Pensando… (10 tokens · 3s)")
    panel.on_answer_complete("resposta final")
    assert not panel._thinking_indicator.isVisibleTo(panel)


def test_indicator_ignored_when_not_generating(qtbot):
    panel = RAGPanel()
    qtbot.addWidget(panel)
    # Sem geração ativa, status residual não deve reabrir o indicador.
    panel.on_status_updated("💭 Pensando… (1 tokens · 0s)")
    assert not panel._thinking_indicator.isVisibleTo(panel)
