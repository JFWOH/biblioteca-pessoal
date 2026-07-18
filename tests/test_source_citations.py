"""Testes do parser/resolvedor de citações do RAG (Tarefa 3.1 — core puro)."""

from src.core.rag.source_citations import (
    Citation,
    normalize,
    parse_citations,
    resolve_citation,
)


# ── parse_citations ────────────────────────────────────────────────────────

def test_parse_simple_citation():
    cits = parse_citations("Como visto em [Dom Casmurro, p. 12].")
    assert len(cits) == 1
    assert cits[0].title == "Dom Casmurro"
    assert cits[0].page == 12
    assert cits[0].raw == "[Dom Casmurro, p. 12]"


def test_parse_span_matches_text():
    text = "abc [Livro, p. 3] def"
    cit = parse_citations(text)[0]
    assert text[cit.start:cit.end] == "[Livro, p. 3]"


def test_parse_title_with_commas():
    # Título com vírgulas internas; o marcador de página está no fim.
    cits = parse_citations("[Guerra, Paz e Amor, p. 340]")
    assert len(cits) == 1
    assert cits[0].title == "Guerra, Paz e Amor"
    assert cits[0].page == 340


def test_parse_page_marker_variants():
    variants = [
        "[A, p. 1]", "[A, p 1]", "[A, pág. 1]", "[A, pag 1]",
        "[A, página 1]", "[A, pagina 1]", "[A, pg. 1]", "[A, pp. 1]",
    ]
    for v in variants:
        cits = parse_citations(v)
        assert len(cits) == 1, v
        assert cits[0].page == 1, v


def test_parse_multiple_citations_in_order():
    cits = parse_citations("[X, p. 2] blah [Y, p. 9] blah [Z, pág. 4]")
    assert [(c.title, c.page) for c in cits] == [("X", 2), ("Y", 9), ("Z", 4)]


def test_parse_accented_title():
    cits = parse_citations("[Ética a Nicômaco, p. 88]")
    assert cits[0].title == "Ética a Nicômaco"
    assert cits[0].page == 88


def test_parse_no_citation():
    assert parse_citations("Sem nenhuma fonte aqui.") == []
    assert parse_citations("") == []


def test_parse_ignores_malformed():
    # Sem número de página → não casa.
    assert parse_citations("[Livro, p. abc]") == []
    # Título vazio → ignorado.
    assert parse_citations("[, p. 3]") == []


# ── normalize ──────────────────────────────────────────────────────────────

def test_normalize_strips_accents_and_case():
    assert normalize("Ética") == normalize("etica")
    assert normalize("  Dom   Casmurro ") == "dom casmurro"


# ── resolve_citation ───────────────────────────────────────────────────────

_BOOKS = [
    {"id": 1, "title": "Dom Casmurro"},
    {"id": 2, "title": "Ética a Nicômaco"},
    {"id": 3, "title": "Python Fluente"},
    {"id": 4, "title": "A Arte da Guerra"},
]


def _cit(title, page=1):
    return Citation(title=title, page=page, start=0, end=0, raw="")


def test_resolve_exact():
    bid, page = resolve_citation(_cit("Dom Casmurro", 12), _BOOKS)
    assert bid == 1
    assert page == 12


def test_resolve_accent_and_case_insensitive():
    bid, _ = resolve_citation(_cit("etica a nicomaco"), _BOOKS)
    assert bid == 2


def test_resolve_partial_word_containment():
    # Título citado é prefixo do título real.
    bid, _ = resolve_citation(_cit("Python"), _BOOKS)
    assert bid == 3


def test_resolve_typo_fuzzy():
    bid, _ = resolve_citation(_cit("Dom Casmuro"), _BOOKS)  # falta um 'r'
    assert bid == 1


def test_resolve_unresolved_returns_none():
    bid, page = resolve_citation(_cit("Livro Inexistente XYZ", 7), _BOOKS)
    assert bid is None
    assert page == 7  # a página é preservada mesmo sem resolver o livro


def test_resolve_no_false_substring():
    # 'arte' NÃO deve casar dentro de 'Bonaparte' via contenção por palavra.
    books = [{"id": 9, "title": "Bonaparte"}]
    bid, _ = resolve_citation(_cit("arte"), books)
    assert bid is None


def test_resolve_empty_title():
    bid, page = resolve_citation(_cit("", 5), _BOOKS)
    assert bid is None
    assert page == 5


def test_resolve_book_without_id_skipped():
    books = [{"title": "Dom Casmurro"}, {"id": 1, "title": "Dom Casmurro"}]
    bid, _ = resolve_citation(_cit("Dom Casmurro"), books)
    assert bid == 1


# ── Fontes clicáveis no RAGPanel (GUI — Tarefa 3.1) ────────────────────────

def test_rag_panel_retrieved_source_is_clickable(qtbot):
    from PyQt6.QtCore import Qt

    from src.gui.widgets.rag_panel import RAGPanel

    panel = RAGPanel()
    qtbot.addWidget(panel)
    panel.on_sources_found([{
        "metadata": {"book_id": 3, "page_number": 11, "title": "Livro"},
        "distance": 0.2, "document": "trecho...",
    }])
    item = panel._sources_list.item(0)
    assert item.data(Qt.ItemDataRole.UserRole) == (3, 11)

    got = []
    panel.source_clicked.connect(lambda b, p: got.append((b, p)))
    panel._on_source_item_clicked(item)
    assert got == [(3, 11)]  # page 0-based (metadado page_number)


def test_rag_panel_source_without_metadata_not_clickable(qtbot):
    from PyQt6.QtCore import Qt

    from src.gui.widgets.rag_panel import RAGPanel

    panel = RAGPanel()
    qtbot.addWidget(panel)
    panel.on_sources_found([{"metadata": {"title": "Sem IDs"}, "distance": 0.5,
                             "document": "x"}])
    item = panel._sources_list.item(0)
    assert item.data(Qt.ItemDataRole.UserRole) is None

    got = []
    panel.source_clicked.connect(lambda b, p: got.append((b, p)))
    panel._on_source_item_clicked(item)
    assert got == []


def test_rag_panel_citation_augments_sources(qtbot):
    from PyQt6.QtCore import Qt

    from src.gui.widgets.rag_panel import RAGPanel

    panel = RAGPanel()
    qtbot.addWidget(panel)
    panel.set_books_provider(lambda: [{"id": 5, "title": "Dom Casmurro"}])
    panel.on_sources_found([])
    panel.on_answer_complete("Como em [Dom Casmurro, p. 12], vemos que...")

    keys = [panel._sources_list.item(i).data(Qt.ItemDataRole.UserRole)
            for i in range(panel._sources_list.count())]
    assert (5, 11) in keys  # p. 12 (1-based) → página 11 (0-based)


def test_rag_panel_unresolved_citation_not_added(qtbot):
    from PyQt6.QtCore import Qt

    from src.gui.widgets.rag_panel import RAGPanel

    panel = RAGPanel()
    qtbot.addWidget(panel)
    panel.set_books_provider(lambda: [{"id": 5, "title": "Dom Casmurro"}])
    panel.on_sources_found([])
    panel.on_answer_complete("Veja [Livro Que Nao Existe, p. 3].")

    keys = [panel._sources_list.item(i).data(Qt.ItemDataRole.UserRole)
            for i in range(panel._sources_list.count())]
    assert all(k is None for k in keys) or len(keys) == 0


# ── Citações clicáveis NO CORPO da resposta (débito 3.1) ───────────────────

def test_rag_panel_body_citation_becomes_anchor(qtbot):
    """Resposta com citação resolvida → âncora AUTO-CONTIDA no corpo
    (href="citation:{book_id}:{page0}" — o alvo vive no próprio documento)."""
    from src.gui.widgets.rag_panel import RAGPanel

    panel = RAGPanel()
    qtbot.addWidget(panel)
    panel.set_books_provider(lambda: [{"id": 5, "title": "Dom Casmurro"}])
    panel.on_sources_found([])
    answer = "Como em [Dom Casmurro, p. 12], vemos que..."
    panel.on_token_received(answer)  # streaming: corpo é preenchido token a token
    panel.on_answer_complete(answer)

    # p. 12 (1-based) → página 11 (0-based), embutida no próprio href
    assert 'href="citation:5:11"' in panel._response_area.document().toHtml()
    # texto continua legível (âncora usa o próprio trecho como rótulo)
    assert "[Dom Casmurro, p. 12]" in panel._response_area.toPlainText()


def test_rag_panel_body_anchor_click_emits_source_clicked(qtbot):
    """Clique simulado numa âncora citation:{book_id}:{page0} → sinal."""
    from PyQt6.QtCore import QUrl

    from src.gui.widgets.rag_panel import RAGPanel

    panel = RAGPanel()
    qtbot.addWidget(panel)

    got = []
    panel.source_clicked.connect(lambda b, p: got.append((b, p)))
    panel._on_citation_anchor_clicked(QUrl("citation:5:11"))
    assert got == [(5, 11)]


def test_rag_panel_body_unresolved_citation_no_anchor(qtbot):
    """Citação não resolvida → sem âncora (texto plano; ADR-005)."""
    from src.gui.widgets.rag_panel import RAGPanel

    panel = RAGPanel()
    qtbot.addWidget(panel)
    panel.set_books_provider(lambda: [{"id": 5, "title": "Dom Casmurro"}])
    panel.on_sources_found([])
    answer = "Veja [Livro Que Nao Existe, p. 3]."
    panel.on_token_received(answer)
    panel.on_answer_complete(answer)

    assert 'href="citation:' not in panel._response_area.document().toHtml()


def test_rag_panel_body_malformed_anchor_is_noop(qtbot):
    """Âncora malformada não emite nada nem quebra (degradação graciosa)."""
    from PyQt6.QtCore import QUrl

    from src.gui.widgets.rag_panel import RAGPanel

    panel = RAGPanel()
    qtbot.addWidget(panel)

    got = []
    panel.source_clicked.connect(lambda b, p: got.append((b, p)))
    panel._on_citation_anchor_clicked(QUrl("citation:99"))          # falta a página
    panel._on_citation_anchor_clicked(QUrl("citation:abc:def"))     # não numérica
    panel._on_citation_anchor_clicked(QUrl("http://example.com"))   # esquema alheio
    assert got == []


def test_rag_panel_citation_spanning_newline_is_linkified(qtbot):
    """Citação quebrada em duas linhas pelo streaming ainda vira âncora —
    a linkificação usa os offsets de Citation.start/end (não busca textual,
    que não atravessa blocos)."""
    from src.gui.widgets.rag_panel import RAGPanel

    panel = RAGPanel()
    qtbot.addWidget(panel)
    panel.set_books_provider(lambda: [{"id": 5, "title": "Dom Casmurro"}])
    panel.on_sources_found([])
    answer = "Como em [Dom\nCasmurro, p. 12] fica claro."
    panel.on_token_received(answer)
    panel.on_answer_complete(answer)

    assert 'href="citation:5:11"' in panel._response_area.document().toHtml()


def test_rag_panel_theme_switch_recolors_existing_anchors(qtbot):
    """Trocar de tema APÓS a resposta recolore as âncoras já renderizadas —
    a cor inicial é embutida no HTML e o QSS de widget não a alcança."""
    from src.gui.widgets.rag_panel import RAGPanel

    panel = RAGPanel()
    qtbot.addWidget(panel)
    panel.set_theme("dark")
    panel.set_books_provider(lambda: [{"id": 5, "title": "Dom Casmurro"}])
    panel.on_sources_found([])
    answer = "Veja [Dom Casmurro, p. 12]."
    panel.on_token_received(answer)
    panel.on_answer_complete(answer)
    assert "#34d399" in panel._response_area.document().toHtml()  # cor do dark

    panel.set_theme("light")
    html = panel._response_area.document().toHtml()
    assert "#047857" in html      # cor do light aplicada às âncoras existentes
    assert "#34d399" not in html  # nenhum resto da cor antiga
