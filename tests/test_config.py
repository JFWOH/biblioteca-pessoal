"""Testes do módulo de configurações."""

import json
import pytest

from src.core.config import ConfigManager, DEFAULT_CONFIG


@pytest.fixture
def config(tmp_path):
    config_path = tmp_path / "config.json"
    return ConfigManager(config_path)


class TestConfigManager:
    """Testes para o gerenciador de configurações."""

    def test_default_values(self, config):
        assert config.theme == "dark"
        assert config.get("reader.font_size") == 14
        assert config.get("library.view_mode") == "grid"

    def test_set_and_get(self, config):
        config.set("reader.font_size", 18)
        assert config.get("reader.font_size") == 18

    def test_dot_notation(self, config):
        config.set("reader.font_family", "Arial")
        assert config.get("reader.font_family") == "Arial"

    def test_persistence(self, tmp_path):
        path = tmp_path / "test_config.json"
        c1 = ConfigManager(path)
        c1.set("theme", "sepia")
        c1.set("reader.font_size", 20)

        # Recarrega
        c2 = ConfigManager(path)
        assert c2.theme == "sepia"
        assert c2.get("reader.font_size") == 20

    def test_theme_property(self, config):
        config.theme = "light"
        assert config.theme == "light"

    def test_default_on_missing_key(self, config):
        assert config.get("nonexistent.key", "fallback") == "fallback"

    def test_deep_merge(self, tmp_path):
        path = tmp_path / "partial.json"
        path.write_text(json.dumps({"theme": "sepia"}), encoding="utf-8")
        c = ConfigManager(path)
        # Deve ter tema sépia mas manter defaults do reader
        assert c.theme == "sepia"
        assert c.get("reader.font_size") == DEFAULT_CONFIG["reader"]["font_size"]

    def test_recent_files(self, config):
        config.add_recent_file("/path/to/book1.pdf")
        config.add_recent_file("/path/to/book2.epub")
        recent = config.get("recent_files")
        assert len(recent) == 2
        assert recent[0] == "/path/to/book2.epub"  # Mais recente primeiro

    def test_recent_files_dedup(self, tmp_path):
        cfg = ConfigManager(tmp_path / "dedup_config.json")
        cfg.add_recent_file("/path/to/book.pdf")
        cfg.add_recent_file("/path/to/other.pdf")
        cfg.add_recent_file("/path/to/book.pdf")  # Repete
        recent = cfg.get("recent_files")
        assert len(recent) == 2
        assert recent[0] == "/path/to/book.pdf"  # Moveu para o topo
