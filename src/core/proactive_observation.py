"""Helpers puros para observações proativas persistidas.

Lógica de mapeamento entre o dict do worker proativo ({tipo, confianca, texto})
e a tabela ``ai_observations`` do ``LibraryDB``. Sem GUI, sem rede, sem Qt
(ADR-006) — testável isoladamente.
"""

from __future__ import annotations

import json
from typing import Any

# Mapa rótulo (PT) → score numérico usado na coluna ``confidence``.
_CONFIDENCE_MAP = {
    "alta": 0.9,
    "média": 0.6,
    "media": 0.6,
    "baixa": 0.3,
}


def confidence_to_float(label: str) -> float:
    """Converte o rótulo de confiança do worker ("Alta"/"Média"/"Baixa") em score.

    Desconhecido/vazio → 0.5 (neutro).
    """
    return _CONFIDENCE_MAP.get((label or "").strip().lower(), 0.5)


def _float_to_confidence(value: float) -> str:
    """Rótulo aproximado a partir do score (usado só quando falta o payload_json)."""
    if value >= 0.8:
        return "Alta"
    if value >= 0.5:
        return "Média"
    return "Baixa"


def obs_dict_from_row(row: dict[str, Any]) -> dict[str, Any]:
    """Reconstrói o dict de exibição a partir de uma linha de ``get_observations``.

    Prioriza ``payload_json`` (o dict original do worker, que preserva o rótulo de
    confiança exato e qualquer enriquecimento). Cai para as colunas normalizadas
    (``kind`` → tipo, ``content`` → texto, ``confidence`` → rótulo) se o JSON
    faltar ou estiver corrompido. Sempre injeta ``id`` e ``page`` da linha para
    permitir dismiss/contexto na UI.
    """
    obs: dict[str, Any] = {}
    raw = row.get("payload_json")
    if raw:
        try:
            parsed = json.loads(raw)
            if isinstance(parsed, dict):
                obs = dict(parsed)
        except (ValueError, TypeError):
            obs = {}

    obs.setdefault("tipo", row.get("kind") or "Observação")
    obs.setdefault("texto", row.get("content") or "")
    if "confianca" not in obs:
        obs["confianca"] = _float_to_confidence(float(row.get("confidence") or 0.0))

    obs["id"] = row.get("id")
    obs["page"] = row.get("page")
    return obs
