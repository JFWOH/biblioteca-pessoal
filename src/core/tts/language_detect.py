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
