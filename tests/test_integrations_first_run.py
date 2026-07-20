"""Testes da rodada E2 — primeira execução transparente e aba Integrações.

Cobre: aba "🔌 Integrações" (comando/JSON de registro do MCP computados por
máquina, roundtrip da chave mcp.allow_writes), auto-import do manual como
livro nº 1 (src/core/first_run.py) e o modo portátil do HF_HOME em main.py.
"""

import json
import sys

import pytest

from src.core.config import ConfigManager
from src.core.first_run import import_manual_if_first_run
from src.gui.settings_dialog import SettingsDialog
from src.main import _apply_portable_env
from src.utils.constants import PROJECT_ROOT


@pytest.fixture
def config(tmp_path):
    return ConfigManager(tmp_path / "config.json")


class TestAbaIntegracoes:
    def _dialog(self, qtbot, config):
        dialog = SettingsDialog(config)
        qtbot.addWidget(dialog)
        return dialog

    def test_aba_existe(self, qtbot, config):
        dialog = self._dialog(qtbot, config)
        titles = [dialog._tabs.tabText(i) for i in range(dialog._tabs.count())]
        assert "🔌 Integrações" in titles

    def test_comando_claude_code_computado_por_maquina(self, qtbot, config):
        dialog = self._dialog(qtbot, config)
        cmd = dialog._mcp_cmd_edit.toPlainText()
        assert "claude mcp add biblioteca" in cmd
        assert "-m src.mcp.server" in cmd
        assert sys.executable in cmd
        assert str(PROJECT_ROOT) in cmd

    def test_snippet_json_valido(self, qtbot, config):
        dialog = self._dialog(qtbot, config)
        payload = json.loads(dialog._mcp_json_edit.toPlainText())
        server = payload["mcpServers"]["biblioteca"]
        assert server["command"] == sys.executable
        assert server["args"] == ["-m", "src.mcp.server"]
        assert server["env"]["PYTHONPATH"] == str(PROJECT_ROOT)

    def test_allow_writes_roundtrip_e_persistencia(self, qtbot, config, tmp_path):
        dialog = self._dialog(qtbot, config)
        assert dialog._mcp_allow_writes.isChecked() is False  # default seguro
        dialog._mcp_allow_writes.setChecked(True)
        dialog._save_and_close()
        assert config.get("mcp.allow_writes") is True
        # set() persiste: um ConfigManager novo (como o do servidor MCP) vê
        reloaded = ConfigManager(tmp_path / "config.json")
        assert reloaded.get("mcp.allow_writes") is True

    def test_carrega_estado_atual_do_config(self, qtbot, tmp_path):
        cfg_path = tmp_path / "config.json"
        cfg_path.write_text(json.dumps({"mcp": {"allow_writes": True}}),
                            encoding="utf-8")
        dialog = self._dialog(qtbot, ConfigManager(cfg_path))
        assert dialog._mcp_allow_writes.isChecked() is True


class _FakeLibrary:
    def __init__(self, result=("livro", True), error=None):
        self.calls: list[str] = []
        self._result = result
        self._error = error

    def import_file(self, path):
        self.calls.append(path)
        if self._error:
            raise self._error
        return self._result


class TestImportDoManual:
    def _pdf(self, tmp_path):
        pdf = tmp_path / "Manual - Biblioteca Pessoal.pdf"
        pdf.write_bytes(b"%PDF-1.4 fake")
        return pdf

    def test_importa_uma_unica_vez(self, config, tmp_path):
        library = _FakeLibrary()
        pdf = self._pdf(tmp_path)
        assert import_manual_if_first_run(library, config, manual_path=pdf) is True
        assert library.calls == [str(pdf)]
        # 2ª chamada (próxima sessão): flag gravado, não reimporta
        assert import_manual_if_first_run(library, config, manual_path=pdf) is False
        assert len(library.calls) == 1

    def test_flag_persiste_entre_sessoes(self, config, tmp_path):
        pdf = self._pdf(tmp_path)
        import_manual_if_first_run(_FakeLibrary(), config, manual_path=pdf)
        reloaded = ConfigManager(config._path)
        assert reloaded.get("app.manual_imported") is True

    def test_sem_pdf_nao_faz_nada_e_nao_grava_flag(self, config, monkeypatch):
        import src.core.first_run as first_run
        monkeypatch.setattr(first_run, "manual_pdf_path", lambda: None)
        library = _FakeLibrary()
        assert first_run.import_manual_if_first_run(library, config) is False
        assert library.calls == []
        assert config.get("app.manual_imported", False) is False

    def test_falha_de_import_nao_grava_flag(self, config, tmp_path):
        pdf = self._pdf(tmp_path)
        library = _FakeLibrary(error=RuntimeError("disco cheio"))
        assert import_manual_if_first_run(library, config, manual_path=pdf) is False
        assert config.get("app.manual_imported", False) is False
        # próxima sessão tenta de novo
        ok_library = _FakeLibrary()
        assert import_manual_if_first_run(ok_library, config, manual_path=pdf) is True

    def test_import_recusado_nao_grava_flag(self, config, tmp_path):
        pdf = self._pdf(tmp_path)
        library = _FakeLibrary(result=(None, False))
        assert import_manual_if_first_run(library, config, manual_path=pdf) is False
        assert config.get("app.manual_imported", False) is False


class TestModoPortatil:
    def test_sem_marcador_nao_mexe_no_ambiente(self, tmp_path, monkeypatch):
        monkeypatch.delenv("HF_HOME", raising=False)
        _apply_portable_env(tmp_path)
        import os
        assert "HF_HOME" not in os.environ

    def test_com_marcador_aponta_cache_para_o_pacote(self, tmp_path, monkeypatch):
        monkeypatch.delenv("HF_HOME", raising=False)
        (tmp_path / "portable.flag").touch()
        _apply_portable_env(tmp_path)
        import os
        assert os.environ["HF_HOME"] == str(tmp_path / "data" / "hf_cache")
        monkeypatch.delenv("HF_HOME", raising=False)

    def test_hf_home_do_usuario_e_preservado(self, tmp_path, monkeypatch):
        monkeypatch.setenv("HF_HOME", r"C:\meu\cache")
        (tmp_path / "portable.flag").touch()
        _apply_portable_env(tmp_path)
        import os
        assert os.environ["HF_HOME"] == r"C:\meu\cache"
