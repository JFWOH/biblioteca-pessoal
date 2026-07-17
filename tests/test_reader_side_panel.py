"""Testes da Tarefa 1.3 (painel lateral recolhível — Sumário/Marcadores).

O default de configuração (``reader.side_panel_visible``) vive em
``src/core/config.py`` — módulo puro (ADR-006, sem Qt), importável normalmente.
A fiação em ``reader_view.py`` é verificada por checagem ESTÁTICA do
código-fonte (o módulo não pode ser importado depois de existir uma
QApplication — ver tests/test_reader_view_guards.py).
"""
import re
from pathlib import Path

from src.core.config import DEFAULT_CONFIG

_READER_VIEW = Path(__file__).resolve().parent.parent / "src" / "gui" / "reader_view.py"


def _src() -> str:
    return _READER_VIEW.read_text(encoding="utf-8")


# ── Default de configuração (core puro, ADR-006) ──────────────────────────

def test_default_config_has_side_panel_visible_true():
    assert DEFAULT_CONFIG["reader"]["side_panel_visible"] is True


def test_config_manager_exposes_side_panel_key(tmp_path):
    """ConfigManager real (sem Qt) resolve a chave via notação com ponto."""
    from src.core.config import ConfigManager

    cfg = ConfigManager(config_path=tmp_path / "config.json")
    assert cfg.get("reader.side_panel_visible", None) is True
    cfg.set("reader.side_panel_visible", False)
    assert cfg.get("reader.side_panel_visible", None) is False
    # persiste em disco e recarrega
    cfg2 = ConfigManager(config_path=tmp_path / "config.json")
    assert cfg2.get("reader.side_panel_visible", None) is False


# ── Fiação em reader_view.py (checagem estática do fonte) ─────────────────

def test_side_panel_toggle_button_wired():
    src = _src()
    assert "_side_panel_toggle_btn" in src
    assert '"📑"' in src
    assert '"Sumário/Marcadores"' in src
    idx = src.index("self._side_panel_toggle_btn = QPushButton")
    window = src[idx:idx + 900]
    assert "setCheckable(True)" in window
    assert "_toggle_side_panel" in window


def test_toggle_side_panel_method_flips_visibility_and_persists():
    src = _src()
    m = re.search(r"def _toggle_side_panel\(self\).*?\n(?=    def )", src, re.DOTALL)
    assert m, "_toggle_side_panel não encontrado"
    body = m.group(0)
    assert "_side_panel_tabs.setVisible" in body
    assert 'config.set("reader.side_panel_visible"' in body


def test_apply_side_panel_visibility_reads_config_with_default_true():
    src = _src()
    m = re.search(r"def _apply_side_panel_visibility\(self\).*?\n(?=    def )", src, re.DOTALL)
    assert m, "_apply_side_panel_visibility não encontrado"
    body = m.group(0)
    assert 'config.get("reader.side_panel_visible", True)' in body
    assert "_side_panel_tabs.setVisible" in body
    assert "_side_panel_toggle_btn.setChecked" in body


def test_side_panel_visibility_restored_on_open_book_and_setup():
    """'restaurado ao abrir o leitor' — aplicado na construção (_setup_ui) E
    em open_book (reabertura de um livro)."""
    src = _src()
    assert src.count("self._apply_side_panel_visibility()") >= 2
    open_book_block = re.search(r"def open_book\(self.*?\n(?=    def )", src, re.DOTALL)
    assert open_book_block and "_apply_side_panel_visibility" in open_book_block.group(0)
