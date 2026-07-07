"""Fase 5 — continuidade do proativo (lógica pura, ADR-006).

Contrato: docs/agents/proativo_continuidade_execution_contract.md §3.
"""
from src.core.proactive_continuity import already_observed_page, build_memory_block


# ── already_observed_page ──────────────────────────────────────────────

def test_page_with_live_observation_is_observed():
    assert already_observed_page([{"content": "x", "dismissed": 0}]) is True


def test_dismissed_observations_do_not_count():
    """Usuário descartou → a página pode receber uma observação nova."""
    assert already_observed_page([{"content": "x", "dismissed": 1}]) is False


def test_empty_or_none_is_not_observed():
    assert already_observed_page([]) is False
    assert already_observed_page(None) is False


# ── build_memory_block ─────────────────────────────────────────────────

def test_memory_block_lists_recent_with_rule_header():
    obs = [
        {"content": "O autor conecta entropia à seta do tempo.", "page": 12},
        {"content": "Referência implícita a Boltzmann.", "page": 9},
    ]
    block = build_memory_block(obs)
    assert "NÃO as repita" in block
    assert "- (p.12) O autor conecta entropia à seta do tempo." in block
    assert "- (p.9) Referência implícita a Boltzmann." in block
    # Ordem preservada (mais recente primeiro, como o banco devolve).
    assert block.index("(p.12)") < block.index("(p.9)")


def test_memory_block_truncates_long_content_and_caps_items():
    obs = [{"content": "x" * 500, "page": i + 1} for i in range(10)]
    block = build_memory_block(obs, max_items=3, max_chars_each=50)
    assert block.count("\n- ") + block.count("- (") >= 3  # 3 itens
    assert block.count("(p.") == 3
    assert "…" in block
    for line in block.splitlines()[1:]:
        assert len(line) <= 50 + len("- (p.10) ") + 1


def test_memory_block_empty_without_observations():
    assert build_memory_block([]) == ""
    assert build_memory_block(None) == ""
    assert build_memory_block([{"content": "   "}]) == ""


def test_memory_block_without_page_number():
    block = build_memory_block([{"content": "Sem página."}])
    assert "- Sem página." in block
