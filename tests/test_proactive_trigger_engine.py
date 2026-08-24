from src.core.proactive_trigger_engine import ProactiveTriggerEngine

def test_trigger_engine_desligado():
    engine = ProactiveTriggerEngine()
    # Nunca deve disparar se estiver desligado
    assert not engine.should_trigger("Texto longo " * 50, 1, "Desligado")

def test_trigger_engine_curto_demais():
    engine = ProactiveTriggerEngine()
    # Não deve disparar se texto < 200 chars, mesmo no modo Estudo
    assert not engine.should_trigger("Curto", 1, "Estudo")

def test_trigger_engine_leve():
    engine = ProactiveTriggerEngine()
    # Leve exige distância >= 5 e > 150 palavras
    long_text = "Palavra " * 160
    # Inicialmente last_page = -100, então dist > 5
    assert engine.should_trigger(long_text, 10, "Leve")

    # Se testar novamente logo em seguida (distância 1), deve ser False
    assert not engine.should_trigger(long_text, 11, "Leve")

def test_trigger_engine_estudo():
    engine = ProactiveTriggerEngine()
    long_text = "Palavra " * 50
    # Estudo dispara quase toda página (dist >= 1) e não requer tantas palavras (>200 chars é suficiente)
    assert engine.should_trigger(long_text, 10, "Estudo")
    assert engine.should_trigger(long_text, 11, "Estudo")
    # Mesma página (dist 0) não dispara
    assert not engine.should_trigger(long_text, 11, "Estudo")


# ── Onda Q: política de frequência por nível (custo por página) ──────────

def test_policy_gaps_by_level():
    """Leve 8 / Moderado 3 / Estudo 1 páginas entre chamadas ao modelo."""
    from src.core.proactive_trigger_engine import _POLICY
    assert _POLICY["Leve"][0] == 8
    assert _POLICY["Moderado"][0] == 3
    assert _POLICY["Estudo"][0] == 1
    # A ordem dos níveis tem que ser monotônica: Leve custa menos que Moderado,
    # que custa menos que Estudo.
    assert _POLICY["Leve"][0] > _POLICY["Moderado"][0] > _POLICY["Estudo"][0]


def _calls_over(intensity: str, pages: int = 24) -> int:
    engine = ProactiveTriggerEngine()
    text = "Palavra " * 200
    return sum(engine.should_trigger(text, p, intensity) for p in range(1, pages + 1))


def test_cost_per_page_dropped_for_leve_and_moderado():
    """24 páginas lidas: antes 5/12/24 chamadas; agora 3/8/24."""
    assert _calls_over("Leve") == 3        # era 5 (gap 5)
    assert _calls_over("Moderado") == 8    # era 12 (gap 2)
    assert _calls_over("Estudo") == 24     # inalterado por contrato do nível


def test_unknown_intensity_never_triggers():
    engine = ProactiveTriggerEngine()
    assert not engine.should_trigger("Palavra " * 200, 5, "Turbo")
