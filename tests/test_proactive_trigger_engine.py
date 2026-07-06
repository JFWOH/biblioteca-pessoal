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
