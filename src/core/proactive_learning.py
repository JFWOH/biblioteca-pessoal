"""Aprendizado do proativo com dispensas (Fase 6 do roadmap de grafo/memória).

O leitor dispensa observações que não o ajudam, e esse sinal
(``ai_observations.dismissed``, por tipo) até agora não alimentava nada.
Este módulo é a lógica PURA do aprendizado (ADR-006: sem Qt, sem SQLite —
as linhas chegam como dicts injetados pela camada GUI):

- :func:`build_preference_block` — bloco de prompt com os tipos de observação
  que o leitor costuma dispensar, para o proativo evitá-los.

A preferência é do LEITOR, não do livro: o chamador agrega observações de
todos os livros (janela recente, com dispensadas incluídas). Decisão do
usuário (2026-07-07): o aprendizado age SÓ via prompt — nenhum tipo é
suprimido ou deixa de ser gerado.

Contrato: docs/agents/aprendizado_dispensas_execution_contract.md.
"""

_PREFERENCE_HEADER = (
    "PREFERÊNCIA DO LEITOR (aprendida das observações que ele dispensou): "
    "EVITE os tipos abaixo — ele quase sempre os descarta:"
)

# Teto de tipos listados no bloco: mantém o prompt curto mesmo com histórico
# sujo (kinds legados/divergentes).
_MAX_KINDS = 3


def build_preference_block(observations: list[dict], min_samples: int = 4,
                           dismiss_threshold: float = 0.6) -> str:
    """Bloco de preferência para o prompt do proativo ("" se nada qualifica).

    Agrega ``kind``/``dismissed`` das linhas de ``ai_observations`` e marca
    como "a evitar" todo tipo com pelo menos ``min_samples`` observações e
    taxa de dispensa ≥ ``dismiss_threshold``. A cláusula "prefira" só entra
    quando o histórico tem algum tipo fora da lista de evitados.
    """
    stats: dict[str, list[int]] = {}  # kind -> [total, dispensadas]
    for obs in (observations or []):
        kind = (obs.get("kind") or "").strip()
        if not kind:
            continue
        counts = stats.setdefault(kind, [0, 0])
        counts[0] += 1
        if obs.get("dismissed"):
            counts[1] += 1

    avoided = [(kind, total, dismissed) for kind, (total, dismissed) in stats.items()
               if total >= min_samples and dismissed / total >= dismiss_threshold]
    if not avoided:
        return ""
    # Todo tipo que qualifica sai da cláusula "prefira", mesmo se o teto de
    # exibição o cortar — senão o bloco recomendaria um tipo que o leitor dispensa.
    avoided_names = {kind for kind, _, _ in avoided}
    # Mais dispensado primeiro (taxa, depois volume) — os piores entram no teto.
    avoided.sort(key=lambda item: (-(item[2] / item[1]), -item[1]))

    lines = [f'- "{kind}" (dispensou {dismissed} de {total})'
             for kind, total, dismissed in avoided[:_MAX_KINDS]]
    block = _PREFERENCE_HEADER + "\n" + "\n".join(lines)

    preferred = sorted(kind for kind in stats if kind not in avoided_names)
    if preferred:
        block += "\nPrefira os tipos: " + ", ".join(f'"{k}"' for k in preferred) + "."
    return block
