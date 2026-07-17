"""Testes da interseção página × conceitos do X-Ray (Tarefa 3.2 — core puro)."""

from src.core.xray import concept_in_text, normalize, page_concepts


def _concepts(*names):
    """Simula a saída de graph_book_concepts (dicts com chave 'concept')."""
    return [{"concept": n, "weight": 1.0, "mentions": 1} for n in names]


# ── concept_in_text ────────────────────────────────────────────────────────

def test_concept_in_text_case_accent_insensitive():
    norm = normalize("A ENTROPIA cresce e a energia dispersa.")
    assert concept_in_text("entropia", norm)
    assert concept_in_text("Energia", norm)


def test_concept_in_text_word_boundary_no_false_positive():
    norm = normalize("Napoleão Bonaparte venceu a batalha.")
    assert not concept_in_text("arte", norm)   # dentro de 'bonaparte'
    assert concept_in_text("bonaparte", norm)


def test_concept_in_text_multiword():
    norm = normalize("O conceito de energia livre de Gibbs é central.")
    assert concept_in_text("energia livre", norm)


def test_concept_in_text_empty():
    assert not concept_in_text("", normalize("qualquer texto"))
    assert not concept_in_text("entropia", "")


# ── page_concepts ──────────────────────────────────────────────────────────

def test_page_concepts_intersection():
    book = _concepts("Entropia", "Termodinâmica", "Fotossíntese")
    page = "Nesta página falamos de entropia e de termodinâmica aplicada."
    matched = page_concepts(page, book)
    names = [c["concept"] for c in matched]
    assert names == ["Entropia", "Termodinâmica"]  # ordem de entrada preservada


def test_page_concepts_empty_page():
    assert page_concepts("", _concepts("Entropia")) == []


def test_page_concepts_no_match():
    assert page_concepts("texto sem conceitos relevantes", _concepts("Entropia")) == []


def test_page_concepts_accepts_plain_strings():
    matched = page_concepts("fala de entropia aqui", ["Entropia", "Outro"])
    assert matched == ["Entropia"]


def test_page_concepts_custom_key():
    book = [{"display_name": "Entropia"}]
    matched = page_concepts("entropia surge", book, name_key="display_name")
    assert matched == book
