"""Reserva Piper (decisão R.4): diretórios portáteis + catálogo pt-BR.

Cobre a ordem de busca de vozes (config > pacote portátil > home do usuário),
o ``health_check`` com voz pré-seedada DENTRO do pacote e o catálogo com as 4
vozes pt-BR oficiais do rhasspy/piper-voices — sem regredir a resolução por
idioma (pt continua caindo na ``pt_BR-faber-medium``).
"""

import os

import pytest

from src.core.config import DEFAULT_CONFIG, ConfigManager
from src.core.tts import piper_provider as pp
from src.core.tts.piper_provider import PiperProvider
from src.core.tts.tts_router import TTSRouter

FAKE_ONNX = b"onnx-fake"


@pytest.fixture
def isolated_home(monkeypatch, tmp_path):
    """Home vazia: os dirs legado (``~/...``) não podem depender da máquina."""
    home = tmp_path / "home"
    home.mkdir()
    monkeypatch.setenv("HOME", str(home))
    monkeypatch.setenv("USERPROFILE", str(home))
    return home


@pytest.fixture
def empty_package_dir(monkeypatch, tmp_path):
    """Pacote portátil SEM voz pré-seedada (padrão dos testes)."""
    pkg = tmp_path / "app" / "data" / "piper" / "models"
    pkg.mkdir(parents=True)
    monkeypatch.setattr(pp, "PACKAGE_MODELS_DIR", str(pkg))
    return pkg


def _config(tmp_path, models_dir=None) -> ConfigManager:
    cfg = ConfigManager(config_path=tmp_path / "config.json")
    if models_dir is not None:
        cfg.set("tts.piper.models_dir", str(models_dir))
    return cfg


def _provider(config) -> PiperProvider:
    provider = PiperProvider(config=config)
    provider._available = True  # não depende da lib/CLI piper instalada
    return provider


# ── Ordem de busca ────────────────────────────────────────────────────


def test_default_config_traz_a_chave_vazia():
    assert DEFAULT_CONFIG["tts"]["piper"]["models_dir"] == ""


def test_model_dirs_ordem_config_pacote_home(tmp_path, isolated_home,
                                             empty_package_dir):
    explicito = tmp_path / "vozes-do-usuario"
    explicito.mkdir()

    dirs = _provider(_config(tmp_path, explicito))._model_dirs()

    assert len(dirs) == 4
    assert dirs[0] == str(explicito)
    assert dirs[1] == str(empty_package_dir)
    assert str(isolated_home) in dirs[2] and dirs[2].endswith("piper-tts/models")
    assert str(isolated_home) in dirs[3] and dirs[3].endswith("piper-models")


def test_model_dirs_sem_config_comeca_no_pacote(tmp_path, isolated_home,
                                                empty_package_dir):
    dirs = _provider(_config(tmp_path))._model_dirs()

    assert len(dirs) == 3
    assert dirs[0] == str(empty_package_dir)


def test_model_dirs_sem_duplicata_quando_config_aponta_o_pacote(
        tmp_path, isolated_home, empty_package_dir):
    dirs = _provider(_config(tmp_path, empty_package_dir))._model_dirs()

    assert len(dirs) == 3
    assert dirs[0] == str(empty_package_dir)


# ── health_check ──────────────────────────────────────────────────────


def test_health_check_acha_voz_no_dir_do_pacote(tmp_path, isolated_home,
                                                empty_package_dir):
    voz = empty_package_dir / "pt_BR-faber-medium.onnx"
    voz.write_bytes(FAKE_ONNX)

    provider = _provider(_config(tmp_path))

    assert provider.health_check() is True
    assert provider._find_default_model() == str(voz)


def test_health_check_acha_voz_no_dir_de_config(tmp_path, isolated_home,
                                                empty_package_dir):
    explicito = tmp_path / "vozes-do-usuario"
    explicito.mkdir()
    voz = explicito / "pt_BR-cadu-medium.onnx"
    voz.write_bytes(FAKE_ONNX)

    provider = _provider(_config(tmp_path, explicito))

    assert provider.health_check() is True
    assert provider._find_default_model() == str(voz)


def test_health_check_falso_sem_nenhuma_voz(tmp_path, isolated_home,
                                            empty_package_dir):
    provider = _provider(_config(tmp_path))

    assert provider.health_check() is False
    assert provider._find_default_model() is None


# ── Catálogo e resolução por idioma ───────────────────────────────────


def test_catalogo_tem_as_quatro_vozes_ptbr(tmp_path, isolated_home,
                                           empty_package_dir):
    ids = [v.voice_id for v in _provider(_config(tmp_path)).available_voices()]

    assert "pt_BR-faber-medium" in ids
    assert "pt_BR-cadu-medium" in ids
    assert "pt_BR-jeff-medium" in ids
    assert "pt_BR-edresson-low" in ids
    # pt-PT entra no catálogo, mas NÃO é pt-BR (idiomas distintos p/ o roteador)
    assert "pt_PT-tugão-medium" in ids


def test_catalogo_lista_faber_como_primeira_pt(tmp_path, isolated_home,
                                               empty_package_dir):
    voices = _provider(_config(tmp_path)).available_voices()
    pt = [v.voice_id for v in voices if v.language.lower().startswith("pt")]

    assert pt[0] == "pt_BR-faber-medium"


@pytest.mark.parametrize("style", ["serene", "didactic", "technical"])
def test_resolucao_pt_continua_na_faber(tmp_path, isolated_home,
                                        empty_package_dir, style):
    router = TTSRouter()
    provider = _provider(_config(tmp_path))

    assert router._resolve_voice(provider, "pt-BR", style) == "pt_BR-faber-medium"


def test_voz_preseedada_filtra_catalogo_e_resolucao(tmp_path, isolated_home,
                                                    empty_package_dir):
    """Pacote com UMA voz: só ela é anunciada e é ela que resolve o pt."""
    (empty_package_dir / "pt_BR-cadu-medium.onnx").write_bytes(FAKE_ONNX)

    provider = _provider(_config(tmp_path))
    router = TTSRouter()

    assert [v.voice_id for v in provider.available_voices()] == ["pt_BR-cadu-medium"]
    assert router._resolve_voice(provider, "pt-BR", "serene") == "pt_BR-cadu-medium"


def test_installed_model_ids_varre_todos_os_dirs(tmp_path, isolated_home,
                                                 empty_package_dir):
    explicito = tmp_path / "vozes-do-usuario"
    explicito.mkdir()
    (explicito / "pt_BR-jeff-medium.onnx").write_bytes(FAKE_ONNX)
    (empty_package_dir / "pt_BR-faber-medium.onnx").write_bytes(FAKE_ONNX)
    legado = os.path.expanduser("~/piper-models")
    os.makedirs(legado, exist_ok=True)
    with open(os.path.join(legado, "en_US-amy-medium.onnx"), "wb") as f:
        f.write(FAKE_ONNX)

    provider = _provider(_config(tmp_path, explicito))

    assert provider._installed_model_ids() == {
        "pt_BR-jeff-medium", "pt_BR-faber-medium", "en_US-amy-medium",
    }
