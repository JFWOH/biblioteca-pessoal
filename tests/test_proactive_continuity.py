"""Fase 5 — continuidade do proativo (lógica pura, ADR-006).

Contrato: docs/agents/proativo_continuidade_execution_contract.md §3.
"""
from src.core.proactive_continuity import (
    already_observed_page,
    build_memory_block,
    page_cache_key,
    trim_page_excerpt,
)


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
    # Conteúdos distintos entre si (o bloco funde equivalentes — ver testes de
    # deduplicação abaixo), cada um longo o bastante para ser truncado.
    obs = [{"content": f"obs {i} " + "x" * 500, "page": i + 1} for i in range(10)]
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


# ── Onda Q: custo do bloco de memória ──────────────────────────────────

def test_memory_block_merges_equivalent_observations():
    """Observação equivalente entra uma vez só — repeti-la é token pago 2x."""
    obs = [
        {"content": "O autor conecta entropia à seta do tempo.", "page": 12},
        {"content": "o AUTOR   conecta entropia à seta do tempo.", "page": 8},
        {"content": "O autor conecta entropia à seta do tempo.", "page": 4},
    ]
    block = build_memory_block(obs)
    assert block.count("(p.") == 1
    assert "(p.12)" in block  # mantém a mais recente


def test_dedup_frees_slots_for_real_memory():
    """A cota de max_items passa a valer memória distinta, não repetição."""
    obs = [{"content": "Mesma observação de sempre.", "page": i} for i in range(1, 5)]
    obs.append({"content": "Referência implícita a Boltzmann.", "page": 99})
    block = build_memory_block(obs, max_items=3)
    # Antes, os 3 slots seriam ocupados pela mesma frase e Boltzmann ficaria
    # de fora; agora o bloco é menor E lembra mais coisa.
    assert block.count("(p.") == 2
    assert "Boltzmann" in block


# ── Onda Q: memo de sessão e teto do trecho ────────────────────────────

def test_page_cache_key_is_stable_for_same_page_and_text():
    a = page_cache_key(7, 12, "Texto  da página.")
    b = page_cache_key(7, 12, "Texto da  página.")  # espaçamento normalizado
    assert a == b


def test_page_cache_key_changes_with_book_page_or_text():
    base = page_cache_key(7, 12, "Texto da página.")
    assert page_cache_key(8, 12, "Texto da página.") != base
    assert page_cache_key(7, 13, "Texto da página.") != base
    assert page_cache_key(7, 12, "Outro texto.") != base
    assert page_cache_key(None, 12, "Texto da página.")  # funciona sem book_id


def test_trim_page_excerpt_leaves_normal_pages_untouched():
    page = "Palavra " * 400  # ~3,2k chars: página densa comum
    assert trim_page_excerpt(page) == page


def test_trim_page_excerpt_caps_pathological_pages_keeping_both_ends():
    page = "INICIO " + ("x" * 40000) + " FIM"
    trimmed = trim_page_excerpt(page)
    assert len(trimmed) < len(page) / 5
    assert trimmed.startswith("INICIO")
    assert trimmed.endswith("FIM")
    assert "[…]" in trimmed
