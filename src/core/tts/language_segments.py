"""Segmentação de texto misto PT/EN em *runs* de idioma, POR SENTENÇA.

Motivação (item 6, rodada final de TTS): uma página majoritariamente em
português pode conter sentenças INTEIRAS em inglês (citações, exemplos). Hoje a
página toda sai numa voz só e as sentenças EN ficam com fonética PT (ou o
inverso). Este módulo agrupa o texto em *runs* contíguos de mesmo idioma para
que a narração troque a voz por SENTENÇA — nunca por palavra.

Decisões de projeto (fixas por pedido do usuário):
  * Granularidade por SENTENÇA. Palavras EN soltas dentro de uma sentença PT
    NÃO trocam a voz — como o idioma é decidido sobre a sentença inteira, um
    termo técnico avulso jamais separa um run.
  * Idioma por sentença via :func:`detect_language_confident` (conservador:
    exige margem clara). Sentença ambígua (``None``) HERDA o idioma do run
    anterior — ou o ``default_lang`` no início do texto.
  * Sentenças consecutivas do mesmo idioma são FUNDIDAS num único run. A
    concatenação dos textos dos runs reconstitui EXATAMENTE o texto de entrada
    (espaços/quebras preservados) — garantido por fatiamento, nunca por
    ``strip``/``join`` reconstrutivo.
  * Guarda-chuva anti-picote: uma sentença só INICIA uma troca de idioma (novo
    run) se for "substancial" — ``>= _MIN_SWITCH_CHARS`` caracteres OU uma
    sentença COMPLETA (termina em pontuação final) detectada com confiança.
    Caso contrário herda o idioma do run corrente. Isso evita picotar a voz em
    fragmentos curtos que a detecção confiante ainda assim classificou.

ADR-006: núcleo puro — sem Qt, sem threads, sem I/O.
"""
from __future__ import annotations

import re

from src.core.tts.language_detect import detect_language_confident

# Fim de FRASE: terminador (. ! ? …) + aspas/parênteses de fecho + espaço(s).
# O ``\s+`` final "prende" o espaço à sentença anterior, de modo que a
# concatenação dos runs reconstitua exatamente o texto de entrada.
_SENTENCE_BOUNDARY = re.compile(r"[.!?…]+[\"'\)\]»”’]*\s+")

# A sentença TERMINA em pontuação final (para o guarda-chuva anti-picote:
# "sentença completa detectada com confiança").
_ENDS_SENTENCE = re.compile(r"[.!?…][\"'\)\]»”’]*\s*$")

# Uma troca de idioma só é permitida para uma sentença "substancial": com pelo
# menos este número de caracteres OU que seja uma sentença completa (ver acima).
_MIN_SWITCH_CHARS = 40


def _primary(language: str) -> str:
    """Subtag primário de um código de idioma ('en-US'→'en', 'pt_BR'→'pt')."""
    if not language:
        return ""
    return language.strip().lower().replace("_", "-").split("-")[0]


def _canonical(language: str) -> str:
    """Normaliza o código para a forma que o roteador de voz espera.

    ``detect_language_confident`` devolve 'pt-BR'/'en-US'; o idioma do perfil
    pode vir como 'pt' ou 'pt-BR'. Canonizamos pt→'pt-BR' e en→'en-US' para que
    um trecho HERDADO do perfil e um trecho DETECTADO no mesmo idioma não virem
    runs distintos. Outros idiomas passam intactos.
    """
    primary = _primary(language)
    if primary == "pt":
        return "pt-BR"
    if primary == "en":
        return "en-US"
    return language or ""


def _split_sentences(text: str) -> list[str]:
    """Fatia ``text`` em pedaços de sentença PRESERVANDO todos os caracteres.

    Cada pedaço inclui o terminador e o espaço em branco que o segue; o último
    pedaço (sem terminador) leva o resto do texto. A concatenação dos pedaços é
    idêntica a ``text`` — o fatiamento nunca descarta nada.
    """
    pieces: list[str] = []
    last = 0
    for match in _SENTENCE_BOUNDARY.finditer(text):
        pieces.append(text[last:match.end()])
        last = match.end()
    if last < len(text):
        pieces.append(text[last:])
    return pieces


def split_language_runs(text: str, default_lang: str) -> list[tuple[str, str]]:
    """Agrupa ``text`` em runs ``(idioma, trecho)`` contíguos por idioma.

    Args:
        text: Texto (idealmente já pré-processado para TTS).
        default_lang: Idioma-base (do perfil). Vale para sentenças ambíguas no
            início e é o rótulo do run quando nada foi detectado ainda.

    Returns:
        Lista de tuplas ``(idioma, trecho)``. A concatenação de todos os
        ``trecho`` reconstitui exatamente ``text``. Para texto vazio, ``[]``.
        Um único idioma ⇒ lista de um elemento só.
    """
    if not text or not text.strip():
        return []

    default = _canonical(default_lang)
    current_lang = default
    runs: list[list[str]] = []

    for sentence in _split_sentences(text):
        stripped = sentence.strip()
        detected = detect_language_confident(stripped) if stripped else None

        if detected is None:
            # Ambíguo / só espaços → herda o idioma do run corrente.
            lang = current_lang
        else:
            detected = _canonical(detected)
            if _primary(detected) != _primary(current_lang):
                # Candidata a TROCA de idioma: só vale se for substancial.
                substantial = (
                    len(stripped) >= _MIN_SWITCH_CHARS
                    or bool(_ENDS_SENTENCE.search(sentence))
                )
                lang = detected if substantial else current_lang
            else:
                lang = current_lang

        current_lang = lang

        if runs and _primary(runs[-1][0]) == _primary(lang):
            runs[-1][1] += sentence
        else:
            runs.append([lang, sentence])

    return [(lang, txt) for lang, txt in runs]
