"""Testes do padrão de colapso da sidebar do Assistente (RAGPanel).

Sintoma (teste real do usuário): na tela do Assistente, a coluna direita
(Indexação/Modelo/Fontes) ocupa espaço à direita por padrão — o usuário quer
o padrão RECOLHIDO. A escolha do usuário deve persistir via ConfigManager
(chave ``rag.sidebar_collapsed``, default True).
"""
from src.core.config import ConfigManager, DEFAULT_CONFIG
from src.gui.widgets.rag_panel import RAGPanel


def test_default_config_has_sidebar_collapsed_true():
    assert DEFAULT_CONFIG["rag"]["sidebar_collapsed"] is True


def test_sidebar_collapsed_by_default_without_config(qtbot):
    """Sem config injetada (uso direto/testes), o padrão embutido já recolhe."""
    panel = RAGPanel()
    qtbot.addWidget(panel)
    assert panel._sidebar_toggle_btn.isChecked() is True
    assert not panel._sidebar_widget.isVisibleTo(panel)


def test_set_config_applies_persisted_collapsed_state(qtbot, tmp_path):
    config = ConfigManager(tmp_path / "config.json")
    config.set("rag.sidebar_collapsed", False)  # usuário tinha expandido antes

    panel = RAGPanel()
    qtbot.addWidget(panel)
    panel.set_config(config)

    assert panel._sidebar_toggle_btn.isChecked() is False
    assert panel._sidebar_widget.isVisibleTo(panel)


def test_set_config_default_still_collapsed(qtbot, tmp_path):
    config = ConfigManager(tmp_path / "config.json")

    panel = RAGPanel()
    qtbot.addWidget(panel)
    panel.set_config(config)

    assert panel._sidebar_toggle_btn.isChecked() is True
    assert not panel._sidebar_widget.isVisibleTo(panel)


def test_toggle_sidebar_persists_choice(qtbot, tmp_path):
    config_path = tmp_path / "config.json"
    config = ConfigManager(config_path)

    panel = RAGPanel()
    qtbot.addWidget(panel)
    panel.set_config(config)

    # Usuário expande a sidebar clicando no botão de alternância.
    panel._sidebar_toggle_btn.click()
    assert panel._sidebar_widget.isVisibleTo(panel)
    assert config.get("rag.sidebar_collapsed") is False

    # Recarrega a config do disco (nova sessão) — preferência persistiu.
    reloaded = ConfigManager(config_path)
    assert reloaded.get("rag.sidebar_collapsed") is False

    # Clica de novo: recolhe e persiste True.
    panel._sidebar_toggle_btn.click()
    assert not panel._sidebar_widget.isVisibleTo(panel)
    assert config.get("rag.sidebar_collapsed") is True


def test_toggle_sidebar_without_config_does_not_crash(qtbot):
    """Sem config injetada, alternar a sidebar não deve levantar erro (ADR-005)."""
    panel = RAGPanel()
    qtbot.addWidget(panel)
    panel._sidebar_toggle_btn.click()
    assert panel._sidebar_widget.isVisibleTo(panel)
