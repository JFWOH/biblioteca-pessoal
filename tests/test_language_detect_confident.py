"""Detecção CONSERVADORA de idioma para o override de voz (rodada 2, item 1).

Regressão-alvo: em traduções PT de livros técnicos, o texto mantém muitos
termos em inglês. A detecção clássica podia classificar esses trechos como
inglês e a narração saía "anglicada" (voz inglesa lendo português).

``detect_language_confident`` só decide com sinal CLARO; texto misto/ambíguo
retorna ``None`` (e aí a voz do perfil prevalece — nunca a voz do idioma errado).
"""
from src.core.tts.language_detect import (
    detect_language,
    detect_language_confident,
)


# ── Caso REAL da regressão (item 1c, obrigatório) ─────────────────────

def test_pt_translation_with_english_tech_terms_is_never_english():
    """Tradução PT salpicada de termos técnicos EN → NUNCA 'en'."""
    text = ("O Power BI usa query folding para otimizar o refresh do dataset "
            "e melhora a performance do dashboard.")
    result = detect_language_confident(text)
    # Aceita 'pt-BR' ou None (ambíguo). O que NÃO pode é virar inglês.
    assert result in (None, "pt-BR")
    assert not (result or "").lower().startswith("en")


def test_pure_english_stays_english():
    text = ("The dataset is refreshed from the source and the query is "
            "optimized for performance with this approach.")
    assert detect_language_confident(text) == "en-US"


# ── Sinais fortes de cada idioma ──────────────────────────────────────

def test_portuguese_with_accents_is_confident_pt():
    assert detect_language_confident(
        "O coração não mente; é uma órfã da emoção.") == "pt-BR"


def test_portuguese_by_stopwords_without_accents():
    # Sem acentos, mas com stopwords PT claras e sem inglês.
    assert detect_language_confident(
        "isto que e uma coisa com os dados para os testes") == "pt-BR"


def test_english_with_single_stray_accent_still_english():
    # Um acento isolado (loanword) não deve virar português.
    assert detect_language_confident(
        "The café is open and the food is great for you and this town") == "en-US"


# ── Ambiguidade → None (não força override) ───────────────────────────

def test_empty_or_blank_is_none():
    assert detect_language_confident("") is None
    assert detect_language_confident("   ") is None


def test_neutral_text_is_none():
    # Sem stopwords/acentos de nenhum idioma.
    assert detect_language_confident("12345 !!! ... foo bar baz") is None


def test_single_accent_without_strong_signal_is_none():
    # Um único diacrítico e nenhuma stopword clara → ambíguo.
    assert detect_language_confident("café") is None


def test_balanced_mixed_signal_is_none():
    # Stopwords PT e EN em proporção próxima → sem margem → None.
    assert detect_language_confident(
        "the query and the dataset para os dados") is None


# ── A versão clássica NÃO muda de semântica (mantém o default) ────────

def test_classic_detect_language_unchanged_defaults():
    assert detect_language("") == "pt-BR"
    assert detect_language("The quick brown fox jumps over the lazy dog and runs") == "en-US"
