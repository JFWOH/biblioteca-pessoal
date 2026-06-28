"""Testes da detecção heurística de idioma para narração TTS."""
from src.core.tts.language_detect import detect_language


def test_detects_portuguese_by_accents():
    assert detect_language("O coração não mente; é uma órfã da emoção.") == "pt-BR"


def test_detects_portuguese_by_stopwords_without_accents():
    # Sem acentos, mas com stopwords claramente em português.
    assert detect_language("isto que e uma coisa para os meninos") == "pt-BR"


def test_detects_english():
    assert detect_language("The quick brown fox jumps over the lazy dog and runs away") == "en-US"


def test_empty_text_returns_default():
    assert detect_language("") == "pt-BR"
    assert detect_language("   ") == "pt-BR"


def test_default_is_configurable():
    assert detect_language("", default="en-US") == "en-US"


def test_ambiguous_falls_back_to_default():
    # Texto neutro sem stopwords/acentos de nenhum idioma → default.
    assert detect_language("12345 !!! ...") == "pt-BR"


def test_english_with_stray_accent_still_english():
    # Um acento isolado (loanword) não deve sobrepor sinal forte de inglês.
    assert detect_language("The café is open and the food is great for you") == "en-US"
