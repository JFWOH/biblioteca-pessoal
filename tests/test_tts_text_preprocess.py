"""Testes da heurística de pausa em títulos/subtítulos (item A dos ajustes).

Cobre a função pura ``mark_heading_pauses`` e sua integração no pipeline
``TTSTextPreprocessor.prepare_for_speech`` — o sintoma real era um título
colado na frase seguinte ("...a vida real. companheirismo Harold e Erica...").
"""
from src.core.tts.text_preprocess import mark_heading_pauses
from src.core.tts.text_preprocessor import TTSTextPreprocessor


# ── Casos que DEVEM receber pausa ─────────────────────────────────────

def test_inline_lowercase_heading_after_sentence_gets_period():
    """Minúscula logo após um fim de frase = título/rótulo intercalado."""
    text = ("Eles buscavam companheirismo na vida real.\n"
            "companheirismo\n"
            "Harold e Erica achavam isso importante para todos.")
    out = mark_heading_pauses(text)
    assert "companheirismo." in out
    # a linha longa de conteúdo não é tocada
    assert "Harold e Erica achavam isso importante para todos." in out


def test_blank_isolated_heading_gets_period():
    text = ("Fim do capítulo anterior.\n\n"
            "O Reencontro\n\n"
            "Eles se viram novamente depois de muitos anos.")
    out = mark_heading_pauses(text)
    assert "O Reencontro." in out


# ── Casos que NÃO podem ser tocados (evitar falso positivo) ───────────

def test_hard_wrapped_prose_is_not_flagged():
    """Parágrafo com quebras simples (soft-wrap) não vira uma sequência de
    títulos: nenhuma linha ganha ponto indevido."""
    text = ("Era uma vez um menino que\n"
            "morava numa casa pequena\n"
            "perto de um grande rio.")
    assert mark_heading_pauses(text) == text


def test_uppercase_fronted_adverbial_after_period_is_not_flagged():
    """"No dia seguinte" (maiúscula após ponto) é começo de frase legítimo —
    NÃO deve ser quebrado, diferente do rótulo em minúscula."""
    text = ("Ele saiu de casa.\n"
            "No dia seguinte\n"
            "Maria chegou muito cedo para a reunião marcada.")
    assert mark_heading_pauses(text) == text


def test_line_already_ending_in_punctuation_is_untouched():
    text = "Introdução:\n\nEste é o conteúdo do capítulo."
    assert mark_heading_pauses(text) == text


def test_single_line_text_is_untouched():
    # Sem quebras não há como delimitar título; frase curta avulsa fica como está.
    assert mark_heading_pauses("Uma frase curta") == "Uma frase curta"


def test_is_idempotent():
    text = ("A vida real.\n"
            "companheirismo\n"
            "Harold e Erica compartilhavam tudo o que tinham.")
    once = mark_heading_pauses(text)
    assert mark_heading_pauses(once) == once


# ── Integração no pipeline completo (todos os caminhos passam por aqui) ─

def test_prepare_for_speech_separates_glued_heading():
    raw = ("Eles queriam entender a vida real.\n"
           "companheirismo\n"
           "Harold e Erica compartilhavam tudo o que tinham.")
    out = TTSTextPreprocessor().prepare_for_speech(raw)
    # Após o colapso das quebras, o título fica como FRASE separada…
    assert "companheirismo." in out
    # …e não mais colado ("companheirismo Harold" era o sintoma).
    assert "companheirismo Harold" not in out


def test_prepare_for_speech_leaves_clean_paragraph_unchanged():
    raw = "Um parágrafo comum, com pontuação correta, que termina bem."
    out = TTSTextPreprocessor().prepare_for_speech(raw)
    assert out == raw
