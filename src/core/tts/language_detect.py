"""Detecção heurística de idioma para narração TTS (português vs inglês).

Sem dependências externas: usa marcadores ortográficos exclusivos do português
(acentos/cedilha) e listas curtas de stopwords. É suficiente para escolher a voz
do narrador entre PT-BR e inglês — não pretende cobrir outros idiomas.
"""
from __future__ import annotations

import re

# Caracteres que praticamente só ocorrem em português (não em inglês).
_PT_CHARS = set("ãõáàâéêíóôúûç")

_PT_STOP = {
    "de", "que", "não", "uma", "com", "para", "os", "as", "dos", "das",
    "ele", "ela", "você", "então", "porque", "também", "já", "está", "são", "ser",
}
_EN_STOP = {
    "the", "and", "of", "to", "is", "in", "that", "it", "for", "with",
    "this", "are", "was", "you", "but", "not", "have", "from", "they", "which",
}

_WORD_RE = re.compile(r"[a-zà-ÿ']+")


def detect_language(text: str, default: str = "pt-BR") -> str:
    """Retorna ``'pt-BR'`` ou ``'en-US'`` para o texto fornecido.

    Usa ``default`` quando o texto é vazio ou o sinal é ambíguo (empate).
    Heurística: caracteres exclusivos do português e stopwords de cada idioma.
    """
    if not text or not text.strip():
        return default

    sample = text[:2000].lower()
    pt_score = sum(1 for c in sample if c in _PT_CHARS)

    words = _WORD_RE.findall(sample)
    pt_score += sum(1 for w in words if w in _PT_STOP)
    en_score = sum(1 for w in words if w in _EN_STOP)

    if en_score == pt_score:
        return default
    return "en-US" if en_score > pt_score else "pt-BR"


# Contagem mínima de stopwords e razão mínima entre idiomas para uma decisão
# CONFIANTE (ver detect_language_confident). Empates fracos → ambíguo.
_CONFIDENT_MIN_STOP = 3
_CONFIDENT_MIN_RATIO = 2


def detect_language_confident(text: str) -> str | None:
    """Detecção CONSERVADORA de idioma, para o OVERRIDE de voz da narração.

    Diferente de :func:`detect_language` (que sempre decide, usando um
    ``default`` no empate), esta só devolve um idioma quando o sinal é CLARO;
    caso ambíguo ou de texto misto retorna ``None`` — e aí a voz do PERFIL do
    usuário prevalece, em vez de forçarmos uma voz do idioma errado.

    Motivação (regressão da rodada anterior): traduções em português de livros
    técnicos mantêm muitos termos em inglês. A heurística clássica classificava
    esses trechos como inglês e a narração saía "anglicada" (voz inglesa lendo
    português). Aqui exigimos margem clara antes de sobrepor a voz.

    Critérios:
      * Sinal PT = diacríticos exclusivos do português + stopwords PT.
        Prosa PT real acumula MUITOS diacríticos; inglês só os traz em raros
        loanwords (café, résumé) — por isso os diacríticos entram no sinal, mas
        a decisão SEMPRE exige margem clara sobre o outro idioma (um punhado de
        loanwords acentuados não sobrepõe um inglês dominante em stopwords).
      * Sinal EN = stopwords EN.
      * Decide só com contagem mínima (``_CONFIDENT_MIN_STOP``) E margem
        (``_CONFIDENT_MIN_RATIO``:1) do vencedor; senão ⇒ ``None`` (ambíguo).

    Retorna ``'pt-BR'``, ``'en-US'`` ou ``None`` (mesma convenção de códigos de
    :func:`detect_language`, para bater com a resolução de voz do TTSRouter).
    """
    if not text or not text.strip():
        return None

    sample = text[:2000].lower()
    words = _WORD_RE.findall(sample)
    if not words:
        return None

    pt_char_count = sum(1 for c in sample if c in _PT_CHARS)
    pt_stop = sum(1 for w in words if w in _PT_STOP)
    en_stop = sum(1 for w in words if w in _EN_STOP)

    pt_signal = pt_char_count + pt_stop
    en_signal = en_stop

    if (pt_signal >= _CONFIDENT_MIN_STOP
            and pt_signal >= _CONFIDENT_MIN_RATIO * max(en_signal, 1)):
        return "pt-BR"
    if (en_signal >= _CONFIDENT_MIN_STOP
            and en_signal >= _CONFIDENT_MIN_RATIO * max(pt_signal, 1)):
        return "en-US"

    return None
