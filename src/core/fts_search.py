"""Lógica pura da busca full-text no CONTEÚDO dos livros (FTS5).

Sem I/O e sem Qt — só a sanitização da query do usuário e os marcadores de
destaque usados pelo ``snippet()`` do FTS5. Fica separado de ``database.py``
para poder ser testado isoladamente (ADR-005: uma query malformada nunca pode
estourar erro de sintaxe do FTS5 — precisa virar "sem resultado").

Marcadores de destaque
----------------------
O ``snippet()`` embrulha os termos casados com ``SNIPPET_OPEN``/``SNIPPET_CLOSE``.
São caracteres de controle (fora de qualquer texto real de livro) de propósito:
a GUI escapa o HTML do trecho ANTES de trocar os marcadores pelas tags de
destaque, então conteúdo do livro com ``<``, ``>`` ou ``&`` nunca quebra o rich
text do Qt. Núcleo e GUI importam as constantes daqui — uma única fonte.
"""

import re

SNIPPET_OPEN = "\x02"
SNIPPET_CLOSE = "\x03"
SNIPPET_ELLIPSIS = "…"

# Pelo menos um caractere de "palavra" (unicode) para o token valer a pena.
_WORDISH = re.compile(r"\w", re.UNICODE)


def sanitize_fts_query(raw: str) -> str:
    """Converte a query do usuário numa expressão MATCH segura do FTS5.

    Estratégia: cada palavra digitada vira uma *frase entre aspas duplas*. Isso
    neutraliza todos os operadores do FTS5 (``AND``/``OR``/``NOT``/``NEAR``,
    ``*``, ``:``, ``^``, ``-``, parênteses) tratando-os como texto literal, e
    lida com aspas embutidas sem gerar sintaxe inválida. As frases são unidas
    por espaço — o que no FTS5 é um ``AND`` implícito (todos os termos precisam
    aparecer na mesma página).

    Termos que, depois de limpos, não têm nenhum caractere de palavra são
    descartados. Se a query inteira for vazia (ou só pontuação/aspas), devolve
    ``""`` — o chamador trata como "sem resultado" e nem chega a rodar o MATCH.

    Não faz prefixo (``termo*``) nem stemming: a busca é por palavra exata
    (com dobra de acentos vinda do tokenizer ``remove_diacritics``).
    """
    if not raw or not raw.strip():
        return ""
    tokens: list[str] = []
    for tok in raw.split():
        # Aspas embutidas viram espaço para não abrir/fechar frase no meio do
        # token; o token pode então virar uma frase de mais de uma palavra, o
        # que é semanticamente aceitável (busca a sequência).
        cleaned = tok.replace('"', " ").strip()
        if not _WORDISH.search(cleaned):
            continue
        tokens.append('"' + cleaned + '"')
    return " ".join(tokens)
