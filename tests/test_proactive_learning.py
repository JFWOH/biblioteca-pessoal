"""Testes do aprendizado com dispensas (Fase 6): lógica pura, sem Qt/SQLite.

Contrato: docs/agents/aprendizado_dispensas_execution_contract.md.
"""
from src.core.proactive_learning import build_preference_block


def _history(kind: str, total: int, dismissed: int) -> list[dict]:
    """total observações do tipo, das quais `dismissed` foram dispensadas."""
    rows = [{"kind": kind, "dismissed": 1} for _ in range(dismissed)]
    rows += [{"kind": kind, "dismissed": 0} for _ in range(total - dismissed)]
    return rows


def test_empty_history_returns_empty():
    assert build_preference_block([]) == ""
    assert build_preference_block(None) == ""


def test_below_min_samples_returns_empty():
    """3 dispensas de 3 ainda é amostra insuficiente (min_samples=4)."""
    assert build_preference_block(_history("Contexto externo", 3, 3)) == ""


def test_rate_below_threshold_returns_empty():
    """50% de dispensa não atinge o limiar de 60%."""
    assert build_preference_block(_history("Contexto externo", 4, 2)) == ""


def test_qualifying_kind_produces_block_with_counts():
    history = _history("Contexto externo", 6, 5) + _history("Observação do texto", 3, 0)
    block = build_preference_block(history)
    assert "EVITE" in block
    assert '"Contexto externo" (dispensou 5 de 6)' in block
    assert 'Prefira os tipos: "Observação do texto".' in block


def test_no_prefer_clause_when_all_kinds_avoided():
    block = build_preference_block(_history("Contexto externo", 5, 5))
    assert '"Contexto externo" (dispensou 5 de 5)' in block
    assert "Prefira" not in block


def test_rows_without_kind_are_ignored():
    history = [{"kind": "", "dismissed": 1}, {"dismissed": 1}, {"kind": None, "dismissed": 1}]
    assert build_preference_block(history * 4) == ""


def test_block_caps_at_three_kinds_worst_rates_first():
    history = (_history("A", 4, 4)      # 100%
               + _history("C", 5, 4)    # 80%
               + _history("B", 4, 3)    # 75%
               + _history("D", 5, 3))   # 60% — qualifica, mas fica fora do teto
    block = build_preference_block(history)
    assert '"A"' in block and '"C"' in block and '"B"' in block
    # D qualifica mas fica fora do teto — e NÃO pode virar recomendação.
    assert '"D"' not in block
    assert "Prefira" not in block
    # Ordem: pior taxa primeiro.
    assert block.index('"A"') < block.index('"C"') < block.index('"B"')


def test_dismissed_truthy_values_count():
    """`dismissed` pode chegar como bool (robustez além do int do SQLite)."""
    history = [{"kind": "Contexto externo", "dismissed": True} for _ in range(4)]
    assert "Contexto externo" in build_preference_block(history)
