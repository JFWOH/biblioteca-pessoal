"""Aprendizado do agente RAG com o feedback (👍/👎) do leitor.

Fase análoga à 6 (proativo aprende com dispensas): um sinal do leitor que
antes não alimentava nada — os 👎 das respostas — agora entra no prompt do
agente como ajuste. Decisão do usuário: o aprendizado age SÓ via prompt;
nenhum comportamento é suprimido por código.

Este módulo é a lógica PURA do aprendizado (ADR-006: sem Qt, sem SQLite).
As linhas de ``agent_feedback`` chegam como dicts injetados pela camada que
tem o banco; aqui elas são apenas lidas.

- :func:`build_feedback_block` — bloco de prompt com ajustes derivados dos
  motivos (chips) que o leitor marcou nos 👎 recentes.
"""

_HEADER = (
    "O leitor avaliou negativamente respostas recentes. "
    "Ajustes com base no feedback:"
)

# Quando há ≥4 negativos mas nenhuma categoria qualifica, o bloco traz este
# único bullet genérico (ainda é um sinal, mas sem motivo dominante).
_GENERIC_BULLET = "Capriche na fundamentação e cite as fontes do livro."

# Motivo canônico (a chave gravada em ``reason`` pelos chips do 👎) → instrução
# de ajuste no prompt. A ORDEM deste dict é também a ordem canônica usada como
# critério de desempate entre categorias com a mesma contagem.
_CATEGORY_INSTRUCTIONS: dict[str, str] = {
    "resposta_errada": (
        "Verifique cada afirmação no conteúdo do livro antes de responder; "
        "sem base no contexto, diga isso explicitamente."
    ),
    "incompleta": (
        "Prefira respostas completas: cubra todos os pontos da pergunta e "
        "cite as fontes (página/trecho) do livro."
    ),
    "fora_contexto": (
        "Restrinja-se ao conteúdo do livro atual e ao contexto fornecido; "
        "evite generalidades externas."
    ),
    "generica": (
        "Evite respostas genéricas: ancore cada resposta em trechos "
        "específicos do contexto."
    ),
}

# Limiares (espelham a filosofia da Fase 6: só age com sinal suficiente).
_MIN_NEGATIVES = 4       # a janela precisa de ≥4 negativos para haver bloco
_MIN_CATEGORY_HITS = 3   # uma categoria qualifica com ≥3 ocorrências
_MAX_CATEGORIES = 2      # no máximo 2 categorias entram no bloco


def _rating_of(row: object) -> float | None:
    """Rating numérico da linha, ou ``None`` se malformada (ADR-005).

    Rejeita não-dicts, ``rating`` ausente/não-numérico e ``bool`` (que em
    Python é subclasse de ``int`` e não representa uma nota real).
    """
    if not isinstance(row, dict):
        return None
    rating = row.get("rating")
    if isinstance(rating, bool) or not isinstance(rating, (int, float)):
        return None
    return float(rating)


def build_feedback_block(rows: list[dict]) -> str | None:
    """Bloco de prompt com ajustes aprendidos dos 👎 do leitor, ou ``None``.

    ``rows`` é a janela recente de ``agent_feedback`` (o chamador limita a
    200, mais recentes primeiro). Negativos = ``rating`` < 0. Com menos de
    ``_MIN_NEGATIVES`` (4) negativos não há sinal suficiente e o resultado é
    ``None`` (sem bloco).

    Só os motivos canônicos (:data:`_CATEGORY_INSTRUCTIONS`) contam como
    categoria, e apenas entre os negativos; cada uma qualifica com
    ``_MIN_CATEGORY_HITS`` (3) ocorrências e entram no máximo
    ``_MAX_CATEGORIES`` (2) no bloco (contagem desc; empate pela ordem
    canônica). Texto livre ("Outro…") não vira categoria — conta só no total
    de negativos. Sem nenhuma categoria qualificada (mas com ≥4 negativos), o
    bloco traz um único bullet genérico. Linhas malformadas são ignoradas.
    """
    negatives = 0
    category_counts: dict[str, int] = {}
    for row in (rows or []):
        rating = _rating_of(row)
        if rating is None or rating >= 0:
            continue
        negatives += 1
        reason = row.get("reason")
        if isinstance(reason, str):
            key = reason.strip()
            if key in _CATEGORY_INSTRUCTIONS:
                category_counts[key] = category_counts.get(key, 0) + 1

    if negatives < _MIN_NEGATIVES:
        return None

    canonical_order = list(_CATEGORY_INSTRUCTIONS)
    qualified = [k for k, n in category_counts.items() if n >= _MIN_CATEGORY_HITS]
    # Contagem desc; empate resolvido pela ordem canônica (determinístico).
    qualified.sort(key=lambda k: (-category_counts[k], canonical_order.index(k)))
    top = qualified[:_MAX_CATEGORIES]

    if top:
        bullets = [_CATEGORY_INSTRUCTIONS[k] for k in top]
    else:
        bullets = [_GENERIC_BULLET]

    return _HEADER + "\n" + "\n".join(f"- {b}" for b in bullets)
