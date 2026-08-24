"""Testes da detecção de hardware multiplataforma + modelo recomendado por tier."""
from unittest.mock import patch

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
    qualidade superior."""
    svc = HardwareCapabilityService()
    assert svc.get_model_for_task("fast") == "gemma4:e4b"


def test_get_model_for_task_deep_matches_recommended_llm_model():
    svc = HardwareCapabilityService()
    svc._cached_tier = "Tier A"
    assert svc.get_model_for_task("deep") == svc.get_recommended_llm_model() == "gemma4:12b"

    svc._cached_tier = "Tier B"
    assert svc.get_model_for_task("deep") == svc.get_recommended_llm_model() == "gemma4:e4b"
