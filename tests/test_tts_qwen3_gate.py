"""Gate de opt-in do provider PESADO Qwen3-TTS (item 11 da rodada UX ago/2026).

Contrato: sem ``tts.qwen3.enabled`` na config, o provider não é construído,
não é registrado no roteador e — o ponto caro — as dependências pesadas
(torch/transformers) NÃO são importadas. Ver src/core/tts/qwen3_tts_provider.py.
"""
import builtins

import pytest

from src.core.config import DEFAULT_CONFIG, ConfigManager
from src.core.tts.base_tts_provider import TTSProviderError
from src.core.tts.qwen3_tts_provider import (
    QWEN3_ENABLED_KEY,
    Qwen3TTSProvider,
    qwen3_gate_enabled,
)
from src.core.tts.tts_router import TTSRouter


_HEAVY = ("torch", "transformers")


def _import_guard(monkeypatch, *, fail_heavy: bool):
    """Instala um __import__ que registra (e barra) os imports pesados."""
    seen: list[str] = []
    real_import = builtins.__import__

    def _hooked(name, *args, **kwargs):
        root = name.split(".")[0]
        if root in _HEAVY:
            seen.append(root)
            if fail_heavy:
                raise ImportError(f"import pesado simulado: {name}")
        return real_import(name, *args, **kwargs)

    monkeypatch.setattr(builtins, "__import__", _hooked)
    return seen


# ── A chave e seu default ──────────────────────────────────────────────────

def test_chave_do_gate_existe_no_default_config_e_vem_desligada():
    assert DEFAULT_CONFIG["tts"]["qwen3"]["enabled"] is False


def test_config_manager_le_a_chave_pelo_caminho_pontilhado(tmp_path):
    cfg = ConfigManager(tmp_path / "config.json")
    assert cfg.get(QWEN3_ENABLED_KEY, None) is False
    cfg.set(QWEN3_ENABLED_KEY, True)
    assert cfg.get(QWEN3_ENABLED_KEY) is True


def test_qwen3_gate_enabled_reflete_a_config(monkeypatch):
    import src.core.config as cfg_mod

    lidas: list[str] = []

    class _FakeCfg:
        def __init__(self, *a, **k):
            pass

        def get(self, key, default=None):
            lidas.append(key)
            return True

    monkeypatch.setattr(cfg_mod, "ConfigManager", _FakeCfg)
    assert qwen3_gate_enabled() is True
    assert lidas == [QWEN3_ENABLED_KEY]


def test_qwen3_gate_fecha_quando_a_config_e_ilegivel(monkeypatch):
    """Falha de leitura → gate FECHADO (conservador: abrir por engano custa torch)."""
    import src.core.config as cfg_mod

    def _boom(*a, **k):
        raise OSError("config indisponível")

    monkeypatch.setattr(cfg_mod, "ConfigManager", _boom)
    assert qwen3_gate_enabled() is False


# ── Gate FECHADO: não constrói, não importa pesado ─────────────────────────

def test_gate_fechado_recusa_a_construcao_sem_importar_torch(monkeypatch):
    seen = _import_guard(monkeypatch, fail_heavy=True)
    with pytest.raises(TTSProviderError) as exc:
        Qwen3TTSProvider(enabled=False)
    assert QWEN3_ENABLED_KEY in str(exc.value)
    assert seen == [], f"gate fechado ainda importou {seen}"


def test_gate_fechado_por_config_tambem_recusa(monkeypatch):
    monkeypatch.setattr(
        "src.core.tts.qwen3_tts_provider.qwen3_gate_enabled", lambda: False)
    with pytest.raises(TTSProviderError):
        Qwen3TTSProvider()


def test_auto_register_nao_registra_qwen3_com_gate_fechado(monkeypatch):
    monkeypatch.setattr(
        "src.core.tts.qwen3_tts_provider.qwen3_gate_enabled", lambda: False)
    router = TTSRouter()
    router.auto_register_providers()   # não pode explodir (ADR-005)
    assert "qwen3-tts" not in router._providers


# ── Gate ABERTO: tenta (e degrada se a dependência faltar) ─────────────────

def test_gate_aberto_tenta_as_dependencias_pesadas(monkeypatch):
    seen = _import_guard(monkeypatch, fail_heavy=True)
    provider = Qwen3TTSProvider(enabled=True)   # ADR-005: não derruba o app
    assert "torch" in seen, "com o gate aberto o provider precisa TENTAR o import"
    assert provider._gate_enabled is True
    # health_check honesto: sem dependências/modelo, continua False.
    assert provider.health_check() is False


def test_auto_register_registra_qwen3_com_gate_aberto(monkeypatch):
    monkeypatch.setattr(
        "src.core.tts.qwen3_tts_provider.qwen3_gate_enabled", lambda: True)
    _import_guard(monkeypatch, fail_heavy=True)   # evita pagar torch de verdade
    router = TTSRouter()
    router.auto_register_providers()
    assert "qwen3-tts" in router._providers


def test_health_check_honesto_mesmo_com_dependencias_presentes(monkeypatch):
    """Gate aberto + deps OK, mas modelo não carregado → health_check False."""
    _import_guard(monkeypatch, fail_heavy=False)
    provider = Qwen3TTSProvider(enabled=True)
    provider._available = True
    provider._model = None
    assert provider.health_check() is False
    provider._model = object()
    provider._processor = object()
    assert provider.health_check() is True
    # Gate fechado retroativamente → volta a ser honesto sobre a indisponibilidade.
    provider._gate_enabled = False
    assert provider.health_check() is False
