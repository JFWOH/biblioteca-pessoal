"""Testes da detecção de hardware multiplataforma + modelo recomendado por tier."""
from unittest.mock import patch

import pytest

import src.core.hardware_capability_service as hw_mod
from src.core.hardware_capability_service import HardwareCapabilityService


def _svc_without_gpu() -> HardwareCapabilityService:
    svc = HardwareCapabilityService()
    return svc


def _sem_torch(monkeypatch):
    """Simula máquina sem torch — o acessor tardio devolve None."""
    monkeypatch.setattr(hw_mod, "get_torch", lambda: None)


def test_low_ram_machine_is_tier_c(monkeypatch):
    _sem_torch(monkeypatch)
    svc = _svc_without_gpu()
    with patch.object(HardwareCapabilityService, "_get_total_ram_gb", return_value=4.0):
        assert svc.get_recommended_tier() == "Tier C"


def test_normal_ram_machine_is_tier_b(monkeypatch):
    _sem_torch(monkeypatch)
    svc = _svc_without_gpu()
    with patch.object(HardwareCapabilityService, "_get_total_ram_gb", return_value=16.0):
        assert svc.get_recommended_tier() == "Tier B"


def test_ram_detection_failure_defaults_to_tier_b(monkeypatch):
    """RAM indetectável (plataforma exótica) → tier padrão, nunca crash (ADR-005)."""
    _sem_torch(monkeypatch)
    svc = _svc_without_gpu()
    with patch.object(HardwareCapabilityService, "_get_total_ram_gb", return_value=None):
        assert svc.get_recommended_tier() == "Tier B"


def test_get_total_ram_gb_returns_positive_on_this_machine():
    """Sanidade real: nesta máquina (qualquer SO suportado) a RAM é detectada."""
    ram = HardwareCapabilityService._get_total_ram_gb()
    assert ram is not None and ram > 0.5


def test_recommended_llm_model_by_tier():
    svc = HardwareCapabilityService()
    svc._cached_tier = "Tier A"
    assert svc.get_recommended_llm_model() == "gemma4:12b"

    svc._cached_tier = "Tier B"
    assert svc.get_recommended_llm_model() == "gemma4:e4b"

    # Tier C: assistente ainda funciona com o modelo leve (só o proativo desliga)
    svc._cached_tier = "Tier C"
    assert svc.get_recommended_llm_model() == "gemma4:e4b"
    assert svc.get_proactive_model_name() == ""


def test_embed_model_constant():
    assert HardwareCapabilityService.EMBED_MODEL == "bge-m3"


def test_get_model_for_task_fast_stays_in_default_family():
    """Tarefas rápidas usam o e4b (mesma família do padrão do app); a
    velocidade vem do think=False no chamador, não de trocar de família —
    benchmark 2026-07-06: e4b think=false empata com gemma3:4b (3,3s) com
    qualidade superior. Sem o modelo de coexistência instalado (onda Q), este
    segue sendo exatamente o comportamento."""
    svc = HardwareCapabilityService()
    with patch.object(HardwareCapabilityService, "fast_task_model_available",
                      return_value=False):
        assert svc.get_model_for_task("fast") == "gemma4:e4b"


def test_get_model_for_task_deep_matches_recommended_llm_model():
    svc = HardwareCapabilityService()
    svc._cached_tier = "Tier A"
    assert svc.get_model_for_task("deep") == svc.get_recommended_llm_model() == "gemma4:12b"

    svc._cached_tier = "Tier B"
    assert svc.get_model_for_task("deep") == svc.get_recommended_llm_model() == "gemma4:e4b"


# ── Coexistência de VRAM nas tarefas rápidas (rodada UX ago/2026, onda Q) ──

def _fake_tags(*models):
    """urlopen falso devolvendo /api/tags com os modelos dados."""
    import io
    import json

    def _urlopen(req, timeout=0):
        return io.BytesIO(
            json.dumps({"models": [{"name": m} for m in models]}).encode())

    return _urlopen


@pytest.fixture(autouse=True)
def _probe_limpa():
    """Sonda de disponibilidade tem cache de CLASSE — zera entre testes."""
    HardwareCapabilityService.reset_fast_task_probe()
    yield
    HardwareCapabilityService.reset_fast_task_probe()


def test_fast_task_prefers_coexisting_model_when_installed(monkeypatch):
    """qwen3.5:4b (~3,4GB) cabe ao lado do modelo de chat em 16GB, então a
    troca chat ↔ tarefa rápida deixa de custar a recarga de ~8GB."""
    monkeypatch.setattr("urllib.request.urlopen",
                        _fake_tags("gemma4:12b", "qwen3.5:4b", "bge-m3"))
    assert HardwareCapabilityService().get_model_for_task("fast") == "qwen3.5:4b"


def test_fast_task_keeps_current_model_when_coexisting_absent(monkeypatch):
    monkeypatch.setattr("urllib.request.urlopen",
                        _fake_tags("gemma4:12b", "gemma4:e4b", "bge-m3"))
    assert HardwareCapabilityService().get_model_for_task("fast") == "gemma4:e4b"


def test_fast_task_ignores_other_tags_of_same_base(monkeypatch):
    """qwen3.5:14b NÃO coexiste — aceitar a base traria a recarga de volta."""
    monkeypatch.setattr("urllib.request.urlopen", _fake_tags("qwen3.5:14b"))
    assert HardwareCapabilityService().get_model_for_task("fast") == "gemma4:e4b"


def test_fast_task_falls_back_when_ollama_is_down(monkeypatch):
    """Daemon fora do ar não pode mudar o modelo nem propagar erro (ADR-005)."""
    def _boom(*a, **k):
        raise OSError("connection refused")

    monkeypatch.setattr("urllib.request.urlopen", _boom)
    assert HardwareCapabilityService().get_model_for_task("fast") == "gemma4:e4b"


def test_probe_result_is_cached_across_instances(monkeypatch):
    """Cada tarefa rápida instancia o serviço de novo: sondar toda vez seria
    um HTTP por flashcard/conceito. O cache é de classe."""
    chamadas = {"n": 0}
    real = _fake_tags("qwen3.5:4b")

    def _contando(req, timeout=0):
        chamadas["n"] += 1
        return real(req, timeout)

    monkeypatch.setattr("urllib.request.urlopen", _contando)
    for _ in range(3):
        assert HardwareCapabilityService().get_model_for_task("fast") == "qwen3.5:4b"
    assert chamadas["n"] == 1


def test_deep_task_never_probes(monkeypatch):
    """Tarefa "deep" usa o modelo do tier — nada de rede no caminho."""
    def _fail(*a, **k):
        raise AssertionError("não deveria sondar o Ollama para tarefa deep")

    monkeypatch.setattr("urllib.request.urlopen", _fail)
    svc = HardwareCapabilityService()
    svc._cached_tier = "Tier B"
    assert svc.get_model_for_task("deep") == "gemma4:e4b"
