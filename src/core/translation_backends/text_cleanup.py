"""Limpeza de artefatos de extração de PDF antes da tradução.

Texto extraído de PDF traz ruído tipográfico que degrada o NLLB (visto em uso
real): capitulares separadas ("W ELCOME"), títulos com letras espaçadas
("C H A P T E R 1"), hifenização de quebra de linha ("inteli-\ngence"). O
modelo tenta "traduzir" o ruído e produz lacunas/trechos não traduzidos.
"""

import re

# Sequência de 3+ letras maiúsculas isoladas ("C H A P T E R") → palavra única.
_SPACED_CAPS_RE = re.compile(r"\b([A-Z])((?:\s[A-Z]\b){2,})")
# Capitular no INÍCIO do texto: "W ELCOME to..." → "WELCOME to...". Restrito ao
# começo para não colar frases legítimas no meio (ex.: "... I HAVE ...").
_DROP_CAP_RE = re.compile(r"^(\s*)([A-Z])\s+([A-Z]{2,})\b")
# Hifenização de quebra de linha: "inteli-\ngence" → "inteligence".
_HYPHEN_BREAK_RE = re.compile(r"(\w)-\s*\n\s*(\w)")


def clean_source_text(text: str) -> str:
    """Normaliza o texto-fonte de uma página/seleção para tradução.

    Inofensivo em texto já limpo; não altera o conteúdo, só os artefatos.
    """
    if not text:
        return ""
    text = _HYPHEN_BREAK_RE.sub(r"\1\2", text)
    text = _SPACED_CAPS_RE.sub(lambda m: (m.group(1) + m.group(2)).replace(" ", ""), text)
    text = _DROP_CAP_RE.sub(r"\1\2\3", text)
    # Espaços repetidos (sem tocar nas quebras de linha, que separam sentenças).
    text = re.sub(r"[ \t]{2,}", " ", text)
    return text.strip()
