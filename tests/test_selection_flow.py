"""Testes da seleção por fluxo de texto no PDF (melhoria de destacar/selecionar).

Antes, a seleção era um retângulo: selecionar uma frase que começa/termina no
meio da linha era inviável (o rect pegava pedaços das linhas vizinhas).
get_selection_flow seleciona como texto normal: 1ª linha do ponto inicial ao
fim, linhas do meio inteiras, última linha até o ponto final — um quad por linha.
"""
import fitz
import pytest

from src.readers.pdf_reader import PDFReader

LINE1 = "a verdade evolucionaria central diz que o inconsciente importa"
LINE2 = "a verdade humanistica diz que a mente consciente pode influenciar"
LINE3 = "estou escrevendo esta historia em primeiro lugar porque sim"


@pytest.fixture
def reader(tmp_path):
    doc = fitz.open()
    page = doc.new_page(width=500, height=300)
    for i, line in enumerate((LINE1, LINE2, LINE3)):
        page.insert_text((50, 100 + i * 20), line, fontsize=11)
    pdf_path = tmp_path / "sel.pdf"
    doc.save(str(pdf_path))
    doc.close()
    r = PDFReader(pdf_path)
    r.open()
    yield r
    r.close()


def _word_center_pct(reader, word: str, occurrence: int = 0) -> tuple[float, float]:
    """Centro (em %) da n-ésima ocorrência da palavra na página 0."""
    page = reader._doc[0]
    pw, ph = page.rect.width, page.rect.height
    # sort=True: mesma ordem de leitura visual usada por get_selection_flow.
    hits = [w for w in page.get_text("words", sort=True) if w[4] == word]
    w = hits[occurrence]
    return ((w[0] + w[2]) / 2 / pw, (w[1] + w[3]) / 2 / ph)


def test_flow_mid_line_to_mid_line(reader):
    """Do meio da linha 1 ao meio da linha 2: fluxo, não retângulo."""
    start = _word_center_pct(reader, "diz", 0)       # linha 1
    end = _word_center_pct(reader, "consciente", 0)  # linha 2
    flow = reader.get_selection_flow(0, start, end)
    assert flow is not None
    assert flow["text"].startswith("diz que o inconsciente importa")
    assert flow["text"].endswith("a mente consciente")
    assert len(flow["quads"]) == 2  # um rect por linha
    q1, q2 = flow["quads"]
    # 1ª linha: começa na âncora (não no início da linha) e vai até o fim dela
    assert q1[0] > 0.15 and q1[2] > q2[2] - 0.5
    # 2ª linha: começa no início da linha
    assert q2[0] < q1[0]


def test_flow_backwards_drag_same_result(reader):
    """Arrasto de baixo para cima devolve a mesma seleção."""
    start = _word_center_pct(reader, "diz", 0)
    end = _word_center_pct(reader, "consciente", 0)
    fwd = reader.get_selection_flow(0, start, end)
    bwd = reader.get_selection_flow(0, end, start)
    assert bwd is not None and bwd["text"] == fwd["text"]


def test_flow_single_line_partial(reader):
    start = _word_center_pct(reader, "verdade", 0)
    end = _word_center_pct(reader, "central", 0)
    flow = reader.get_selection_flow(0, start, end)
    assert flow["text"] == "verdade evolucionaria central"
    assert len(flow["quads"]) == 1


def test_flow_three_lines_middle_full(reader):
    start = _word_center_pct(reader, "importa", 0)   # fim da linha 1
    end = _word_center_pct(reader, "escrevendo", 0)  # início da linha 3
    flow = reader.get_selection_flow(0, start, end)
    assert len(flow["quads"]) == 3
    assert LINE2 in flow["text"]  # linha do meio inteira


def test_flow_empty_area_returns_none(reader):
    """Área sem palavras (margem) → None (chamador usa o rect legado)."""
    assert reader.get_selection_flow(0, (0.01, 0.9), (0.05, 0.95)) is None


def test_flow_invalid_page_returns_none(reader):
    assert reader.get_selection_flow(99, (0.5, 0.5), (0.6, 0.6)) is None


def test_flow_ignores_footer_stored_before_body(tmp_path):
    """Regressão do bug relatado: selecionar um parágrafo traduzia a página
    inteira, começando pelo número do rodapé ("22 A Mente..."). Causa: o
    rodapé fica em um bloco anterior ao corpo no PDF; ordenar por
    (block, line, word) — ordem de ARMAZENAMENTO — faz o rodapé "vazar"
    para dentro de qualquer seleção do corpo. Fix: get_text(..., sort=True)
    usa a ordem visual (topo→baixo). Este PDF insere o RODAPÉ PRIMEIRO
    (block_no menor) e o corpo DEPOIS, replicando a condição do bug.
    """
    doc = fitz.open()
    page = doc.new_page(width=500, height=300)
    page.insert_text((50, 280), "22", fontsize=9)  # rodapé: 1º bloco, no fim visual
    for i, line in enumerate((LINE1, LINE2, LINE3)):  # corpo: blocos depois, no topo
        page.insert_text((50, 100 + i * 20), line, fontsize=11)
    pdf_path = tmp_path / "footer_first.pdf"
    doc.save(str(pdf_path))
    doc.close()

    r = PDFReader(pdf_path)
    r.open()
    try:
        start = _word_center_pct(r, "diz", 0)      # meio da linha 1 do corpo
        end = _word_center_pct(r, "importa", 0)    # fim da linha 1 do corpo
        flow = r.get_selection_flow(0, start, end)
        assert flow is not None
        assert "22" not in flow["text"].split()  # rodapé não vaza para a seleção
        assert flow["text"] == "diz que o inconsciente importa"
    finally:
        r.close()


def test_render_highlight_with_quads(reader):
    """Destaque com quads renderiza sem erro (um annot, multi-linha)."""
    import json
    reader.highlights = [{
        "page_number": 0,
        "annotation_type": "highlight",
        "highlight_color": "#fbbf24",
        "position_data": json.dumps({
            "coords": [0.1, 0.3, 0.9, 0.45],
            "quads": [[0.3, 0.30, 0.9, 0.36], [0.1, 0.37, 0.6, 0.43]],
        }),
    }]
    content = reader.get_page(0)
    assert content.content_type == "image" and len(content.content) > 100
    # Annots temporários foram removidos após o render
    assert not list(reader._doc[0].annots())


def test_render_highlight_legacy_coords_still_works(reader):
    import json
    reader.highlights = [{
        "page_number": 0,
        "annotation_type": "highlight",
        "highlight_color": "#34d399",
        "position_data": json.dumps({"coords": [0.1, 0.3, 0.9, 0.4]}),
    }]
    content = reader.get_page(0)
    assert content.content_type == "image" and len(content.content) > 100
