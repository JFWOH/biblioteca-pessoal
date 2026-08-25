"""Chips de perguntas sugeridas do painel de chat (rodada UX ago/2026, onda S).

Custo LLM ZERO: as perguntas saem dos conceitos do livro aberto no grafo (a
mesma fonte do X-Ray), entregues ao painel por um provedor injetado pelo host
(``set_concepts_provider``, ADR-006 — o painel não conhece DB/GraphStore).
Sem provedor, sem conceitos ou com provedor que levanta: nenhum chip e nenhum
estado de erro (ADR-005).
"""

from src.gui.widgets.rag_panel import RAGPanel


def _provider(*concepts):
    """Provedor falso com a assinatura de ``MainWindow._book_graph_concepts``."""
    return lambda limit=10: list(concepts)[:limit]


# ── Geração dos chips ──────────────────────────────────────────────────────

def test_no_chips_without_provider(qtbot):
    panel = RAGPanel()
    qtbot.addWidget(panel)
    assert panel._suggestion_btns == []
    assert not panel._suggestions_row.isVisibleTo(panel)


def test_no_chips_when_graph_has_no_concepts(qtbot):
    """Livro não ingerido no grafo: some a linha inteira, sem aviso de erro."""
    panel = RAGPanel()
    qtbot.addWidget(panel)
    panel.set_concepts_provider(_provider())
    assert panel._suggestion_btns == []
    assert not panel._suggestions_row.isVisibleTo(panel)


def test_provider_failure_degrades_to_no_chips(qtbot):
    def boom(limit=10):
        raise RuntimeError("grafo indisponível")

    panel = RAGPanel()
    qtbot.addWidget(panel)
    panel.set_concepts_provider(boom)
    assert panel._suggestion_btns == []
    assert not panel._suggestions_row.isVisibleTo(panel)


def test_chips_generated_from_concepts(qtbot):
    panel = RAGPanel()
    qtbot.addWidget(panel)
    panel.set_concepts_provider(_provider("Entropia", "Termodinâmica", "Calor"))

    assert len(panel._suggestion_btns) == 4      # teto de chips
    assert panel._suggestions_row.isVisibleTo(panel)
    # Formato 1 ("O que é X?") para os conceitos; formato 2 (relação com o
    # livro) só para o conceito mais forte, logo em seguida.
    tooltips = [b.toolTip() for b in panel._suggestion_btns]
    assert tooltips[0] == "O que é Entropia?"
    assert tooltips[1] == "Como Entropia se relaciona com o livro?"
    assert tooltips[2] == "O que é Termodinâmica?"


def test_single_concept_still_yields_two_chips(qtbot):
    panel = RAGPanel()
    qtbot.addWidget(panel)
    panel.set_concepts_provider(_provider("Entropia"))
    assert [b.toolTip() for b in panel._suggestion_btns] == [
        "O que é Entropia?",
        "Como Entropia se relaciona com o livro?",
    ]


def test_long_concept_label_is_elided_but_question_is_whole(qtbot):
    """O rótulo curto protege a largura do painel; a pergunta enviada é inteira."""
    longo = "Determinismo Tecnológico Contemporâneo"
    panel = RAGPanel()
    qtbot.addWidget(panel)
    panel.set_concepts_provider(_provider(longo))
    chip = panel._suggestion_btns[0]
    assert chip.text().endswith("…")
    assert len(chip.text()) <= 26
    assert chip.toolTip() == f"O que é {longo}?"


# ── Clique → fluxo normal de envio ─────────────────────────────────────────

def test_chip_click_sends_the_question(qtbot):
    panel = RAGPanel()
    qtbot.addWidget(panel)
    panel.set_concepts_provider(_provider("Entropia"))
    emitted = []
    panel.query_requested.connect(emitted.append)

    panel._suggestion_btns[1].click()

    assert emitted == ["Como Entropia se relaciona com o livro?"]
    assert panel._is_generating


def test_chip_click_ignored_while_generating(qtbot):
    panel = RAGPanel()
    qtbot.addWidget(panel)
    panel.set_concepts_provider(_provider("Entropia"))
    emitted = []
    panel.query_requested.connect(emitted.append)

    panel._set_generating(True)
    panel._suggestion_btns[0].click()
    assert emitted == []


def test_chips_hidden_while_generating_and_back_after(qtbot):
    panel = RAGPanel()
    qtbot.addWidget(panel)
    panel.set_concepts_provider(_provider("Entropia"))

    panel._set_generating(True)
    assert not panel._suggestions_row.isVisibleTo(panel)
    panel._set_generating(False)
    assert panel._suggestions_row.isVisibleTo(panel)


# ── Reação à troca de livro ────────────────────────────────────────────────

def test_chips_follow_the_open_book(qtbot):
    """Trocar de livro refaz os chips; virar página, não."""
    concepts_by_book = {1: ["Entropia"], 2: ["Sinédoque"]}
    current = {"book_id": 1}
    calls = []

    def provider(limit=10):
        calls.append(current["book_id"])
        return concepts_by_book[current["book_id"]][:limit]

    panel = RAGPanel()
    qtbot.addWidget(panel)
    panel.set_concepts_provider(provider)

    panel.set_reading_context(1, "Livro A", 1, "texto")
    assert panel._suggestion_btns[0].toolTip() == "O que é Entropia?"

    calls.clear()
    panel.set_reading_context(1, "Livro A", 2, "outra página")
    assert calls == [], "virar página não re-consulta o grafo"

    current["book_id"] = 2
    panel.set_reading_context(2, "Livro B", 1, "texto")
    assert panel._suggestion_btns[0].toolTip() == "O que é Sinédoque?"


def test_clearing_reading_context_drops_chips(qtbot):
    concepts = {"open": True}

    def provider(limit=10):
        return ["Entropia"] if concepts["open"] else []

    panel = RAGPanel()
    qtbot.addWidget(panel)
    panel.set_concepts_provider(provider)
    assert panel._suggestion_btns

    concepts["open"] = False          # host fechou o livro
    panel.clear_reading_context()
    assert panel._suggestion_btns == []
    assert not panel._suggestions_row.isVisibleTo(panel)
