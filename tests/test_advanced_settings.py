"""Testes da aba "Avançado" do SettingsDialog (Onda 4, item 4.1).

Cobre graph.*, auto_index.* e translation.* — leitura dos defaults,
persistência via ``_save_and_close`` e o mapeamento vazio↔None de
``graph.llm_model`` (lineedit com placeholder "padrão do sistema").
"""
import pytest

from src.core.config import ConfigManager, DEFAULT_CONFIG
from src.gui.settings_dialog import SettingsDialog


@pytest.fixture
def config(tmp_path):
    return ConfigManager(tmp_path / "config.json")


def test_advanced_tab_loads_defaults(qtbot, config):
    dialog = SettingsDialog(config)
    qtbot.addWidget(dialog)

    graph_defaults = DEFAULT_CONFIG["graph"]
    assert dialog._adv_graph_enabled.isChecked() == graph_defaults["enabled"]
    assert dialog._adv_graph_use_llm_pages.isChecked() == graph_defaults["use_llm_pages"]
    assert dialog._adv_graph_use_llm_annotations.isChecked() == graph_defaults["use_llm_annotations"]
    assert dialog._adv_graph_idle_batch_pages.value() == graph_defaults["idle_batch_pages"]
    assert dialog._adv_graph_edge_min_shared.value() == graph_defaults["edge_min_shared"]
    assert dialog._adv_graph_edge_df_cap.value() == pytest.approx(graph_defaults["edge_df_cap"])

    # llm_model é None por padrão → lineedit vazio, com placeholder explicativo.
    assert dialog._adv_graph_llm_model.text() == ""
    assert dialog._adv_graph_llm_model.placeholderText() == "padrão do sistema"

    autoindex_defaults = DEFAULT_CONFIG["auto_index"]
    assert dialog._adv_autoindex_enabled.isChecked() == autoindex_defaults["enabled"]
    assert dialog._adv_autoindex_idle_interval.value() == autoindex_defaults["idle_interval_s"]
    assert dialog._adv_autoindex_idle_min_inactivity.value() == autoindex_defaults["idle_min_inactivity_s"]

    translation_defaults = DEFAULT_CONFIG["translation"]
    assert dialog._adv_translation_model.text() == translation_defaults["model"]
    assert dialog._adv_translation_default_src.text() == translation_defaults["default_src"]
    assert dialog._adv_translation_default_tgt.text() == translation_defaults["default_tgt"]
    assert dialog._adv_translation_revise_llm.isChecked() == translation_defaults["revise_with_llm"]


def test_advanced_tab_saves_graph_settings(qtbot, config):
    dialog = SettingsDialog(config)
    qtbot.addWidget(dialog)

    dialog._adv_graph_enabled.setChecked(False)
    dialog._adv_graph_use_llm_idle.setChecked(True)
    dialog._adv_graph_idle_batch_pages.setValue(50)
    dialog._adv_graph_edge_df_cap.setValue(0.75)
    dialog._save_and_close()

    assert config.get("graph.enabled") is False
    assert config.get("graph.use_llm_idle") is True
    assert config.get("graph.idle_batch_pages") == 50
    assert config.get("graph.edge_df_cap") == pytest.approx(0.75)


def test_advanced_tab_llm_model_empty_maps_to_none(qtbot, config):
    dialog = SettingsDialog(config)
    qtbot.addWidget(dialog)

    dialog._adv_graph_llm_model.setText("   ")  # só espaços → tratado como vazio
    dialog._save_and_close()

    assert config.get("graph.llm_model") is None


def test_advanced_tab_llm_model_roundtrip(qtbot, config):
    dialog = SettingsDialog(config)
    qtbot.addWidget(dialog)
    dialog._adv_graph_llm_model.setText("gemma3:4b")
    dialog._save_and_close()
    assert config.get("graph.llm_model") == "gemma3:4b"

    dialog2 = SettingsDialog(config)
    qtbot.addWidget(dialog2)
    assert dialog2._adv_graph_llm_model.text() == "gemma3:4b"


def test_advanced_tab_saves_autoindex_settings(qtbot, config):
    dialog = SettingsDialog(config)
    qtbot.addWidget(dialog)

    dialog._adv_autoindex_enabled.setChecked(False)
    dialog._adv_autoindex_idle_interval.setValue(300)
    dialog._save_and_close()

    assert config.get("auto_index.enabled") is False
    assert config.get("auto_index.idle_interval_s") == 300


def test_advanced_tab_saves_translation_settings(qtbot, config):
    dialog = SettingsDialog(config)
    qtbot.addWidget(dialog)

    dialog._adv_translation_default_src.setText("es")
    dialog._adv_translation_default_tgt.setText("pt")
    dialog._adv_translation_revise_llm.setChecked(False)
    dialog._save_and_close()

    assert config.get("translation.default_src") == "es"
    assert config.get("translation.default_tgt") == "pt"
    assert config.get("translation.revise_with_llm") is False
