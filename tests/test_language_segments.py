"""Tarefa A (item 6) — segmentação de texto misto PT/EN em *runs* de idioma.

``split_language_runs(text, default_lang)`` agrupa o texto em runs contíguos de
mesmo idioma (decisão POR SENTENÇA, nunca por palavra). Estes testes fixam:
  * a reconstituição EXATA do texto (a concatenação dos runs == entrada);
  * a herança de idioma em sentenças ambíguas (e o ``default_lang`` no início);
  * o guarda-chuva anti-picote (fragmento curto sem pontuação herda);
  * que palavra EN solta numa sentença PT NÃO troca a voz.

Offline, puro (ADR-006): sem Qt, sem TTS real.
"""
from src.core.tts.language_segments import split_language_runs


def _langs(runs):
    return [lang for lang, _ in runs]


def _reconstructs(text, default="pt-BR"):
    runs = split_language_runs(text, default)
    return "".join(txt for _, txt in runs) == text


# ── Vazio / trivial ────────────────────────────────────────────────────

def test_empty_returns_no_runs():
    assert split_language_runs("", "pt-BR") == []
    assert split_language_runs("   \n  ", "pt-BR") == []


def test_single_language_is_one_run():
    text = "Ele disse que não era para todos os alunos da turma."
    runs = split_language_runs(text, "pt-BR")
    assert _langs(runs) == ["pt-BR"]
    assert runs[0][1] == text


# ── Reconstituição exata (inclui espaços/quebras) ──────────────────────

def test_reconstructs_mixed_three_runs():
    text = ("Ele disse que não era para todos. "
            "The book is on the table and it is good. "
            "Então ela foi embora daqui.")
    runs = split_language_runs(text, "pt-BR")
    assert _langs(runs) == ["pt-BR", "en-US", "pt-BR"]
    assert "".join(txt for _, txt in runs) == text


def test_reconstructs_across_paragraph_break():
    text = ("Primeiro parágrafo que não termina aqui agora.\n\n"
            "The second paragraph is here and it is written now.")
    runs = split_language_runs(text, "pt-BR")
    assert _langs(runs) == ["pt-BR", "en-US"]
    # A quebra dupla é preservada (fica presa ao fim do run anterior).
    assert "".join(txt for _, txt in runs) == text


def test_reconstructs_no_trailing_punctuation():
    text = "The book is on the table and it is good and it is here"
    assert _reconstructs(text)


# ── Herança de idioma ──────────────────────────────────────────────────

def test_ambiguous_sentence_inherits_previous_run():
    # 'Bem.' é ambíguo (sem stopwords/diacríticos) → herda o run anterior.
    text = "The book is on the table and it is good. Bem. It stays english here."
    runs = split_language_runs(text, "pt-BR")
    # Um único run EN: 'Bem.' herda o inglês do run corrente.
    assert _langs(runs) == ["en-US"]
    assert "".join(txt for _, txt in runs) == text


def test_first_ambiguous_sentence_uses_default_lang():
    text = "Bem. Ele disse que não era para todos os presentes."
    # default EN: 'Bem.' herda EN, depois troca para PT na sentença confiante.
    assert _langs(split_language_runs(text, "en-US")) == ["en-US", "pt-BR"]
    # default PT: tudo PT.
    assert _langs(split_language_runs(text, "pt-BR")) == ["pt-BR"]


# ── Guarda-chuva anti-picote ───────────────────────────────────────────

def test_short_confident_fragment_without_terminator_inherits():
    # Trecho final 'the is it' é EN-confiante mas curto (<40) e SEM pontuação
    # final → herda o PT do run anterior (não picota a voz).
    text = "Ele disse que não era para todos. the is it"
    assert _langs(split_language_runs(text, "pt-BR")) == ["pt-BR"]


def test_short_confident_complete_sentence_switches():
    # Mesmo curto, uma sentença COMPLETA (com ponto) detectada com confiança
    # inicia um novo run.
    text = "Ele disse que não era para todos. the is it."
    assert _langs(split_language_runs(text, "pt-BR")) == ["pt-BR", "en-US"]


# ── Granularidade por SENTENÇA (nunca por palavra) ─────────────────────

def test_english_word_inside_portuguese_sentence_does_not_switch():
    text = "Ele usou a palavra design que não era para todos os presentes."
    assert _langs(split_language_runs(text, "pt-BR")) == ["pt-BR"]


# ── Fusão de sentenças consecutivas do mesmo idioma ────────────────────

def test_consecutive_same_language_sentences_merge():
    text = ("Ele disse que não era para todos. "
            "Ela também achava que não era justo.")
    runs = split_language_runs(text, "pt-BR")
    assert len(runs) == 1
    assert runs[0][0] == "pt-BR"
    assert runs[0][1] == text
