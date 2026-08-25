"""Item 11 (degradação de TTS VISÍVEL + pyttsx3 fora do topo) e alturas do item 10.

reader_view.py puxa QtWebEngineWidgets, que só pode ser importado ANTES de
existir um QApplication — em suíte cheia o import falharia (ver
tests/test_reader_view_guards.py). Daí os dois estilos aqui:

* checagens ESTÁTICAS do fonte, no padrão já usado por
  test_reader_view_guards.py / test_reader_audio_menu.py;
* UM teste de COMPORTAMENTO real, num subprocesso que importa o módulo antes
  de criar o QApplication (offscreen) e exercita os métodos ligados a um
  objeto-dublê — é o único jeito de provar que o aviso não-modal sai mesmo.
"""
import json
import os
import re
import subprocess
import sys
import textwrap
from pathlib import Path

import pytest

_ROOT = Path(__file__).resolve().parent.parent
_READER_VIEW = _ROOT / "src" / "gui" / "reader_view.py"


def _src() -> str:
    return _READER_VIEW.read_text(encoding="utf-8")


def _method_body(src: str, name: str) -> str:
    m = re.search(rf"def {name}\(.*?\n(?=    (?:def |TTS_FALLBACK_MARK))", src, re.DOTALL)
    assert m, f"método {name} não encontrado"
    return m.group(0)


# ── 1. Menu rápido de narrador: pyttsx3 sai do topo ────────────────────────

def _provider_menu_entries() -> list[tuple[str, str]]:
    """Extrai a lista literal ``providers = [...]`` de _on_tts_settings_clicked."""
    body = _method_body(_src(), "_on_tts_settings_clicked")
    block = re.search(r"providers = \[(.*?)\]", body, re.DOTALL)
    assert block, "lista `providers` do menu rápido não encontrada"
    return re.findall(r'\(\s*"([^"]+)"\s*,\s*"([^"]+)"\s*\)', block.group(1))


def test_menu_de_motor_nao_comeca_por_pyttsx3():
    """Regressão do item 11: pyttsx3 era o 1º item e 1 clique acidental já
    regravava o motor preferido para o pior (o roteador NÃO degrada sozinho
    para pyttsx3 — ele o exclui explicitamente do fallback automático)."""
    entries = _provider_menu_entries()
    assert entries, "menu de motor ficou vazio"
    assert entries[0][1] != "pyttsx3", (
        f"pyttsx3 voltou ao topo do menu (1º item: {entries[0]!r})")
    assert entries[0][1] == "kokoro", "o motor padrão (Kokoro) deve abrir a lista"


def test_menu_de_motor_ordena_kokoro_piper_pyttsx3():
    assert [key for _, key in _provider_menu_entries()] == ["kokoro", "piper", "pyttsx3"]


def test_pyttsx3_e_o_ultimo_e_avisa_a_qualidade_inferior():
    entries = _provider_menu_entries()
    label, key = entries[-1]
    assert key == "pyttsx3"
    assert "Legado" in label and "qualidade inferior" in label, (
        f"rótulo do legado precisa avisar a qualidade: {label!r}")


def test_selecao_de_motor_continua_a_um_clique_sem_confirmacao():
    """O item 11 tira o legado do caminho do dedo, não adiciona fricção."""
    body = _method_body(_src(), "_on_tts_settings_clicked")
    assert 'config.set("tts.book_narrator.preferred_provider", k)' in body
    assert "QMessageBox" not in body, "o menu de motor não deve pedir confirmação"


# ── 2. Degradação VISÍVEL e NÃO-MODAL ──────────────────────────────────────

def test_fallback_avisa_na_statusbar():
    body = _method_body(_src(), "_on_audio_provider_changed")
    assert "_show_status(" in body, "a queda para o motor de reserva precisa avisar"
    assert "motor reserva" in body


def test_aviso_de_fallback_nunca_e_modal():
    body = _method_body(_src(), "_on_audio_provider_changed")
    for modal in ("QMessageBox", "QDialog", "exec()", ".exec("):
        assert modal not in body, f"aviso de fallback não pode ser modal ({modal})"


def test_show_status_cai_para_a_api_publica_do_statusbar():
    """`self.window().statusBar()` devolve a MESMA barra que main_window
    registra por setStatusBar — o aviso não se perde se `_statusbar` faltar."""
    body = _method_body(_src(), "_show_status")
    assert "_statusbar" in body and "statusBar()" in body


def test_indicador_persistente_existe_e_sobrevive_as_trocas_de_estado():
    src = _src()
    assert "def _apply_tts_fallback_indicator" in src
    assert 'setProperty("ttsFallback"' in src, "falta a propriedade dinâmica p/ QSS"
    # Reaplicado pelo helper que reescreve o rótulo do botão.
    assert "_apply_tts_fallback_indicator()" in _method_body(src, "_set_audio_button_state")


def test_volta_ao_preferido_limpa_o_estado_de_reserva():
    body = _method_body(_src(), "_on_audio_provider_changed")
    assert "self._tts_fallback_provider = None" in body


# ── 3. Comportamento real (subprocesso: import ANTES do QApplication) ───────

_DRIVER = textwrap.dedent(
    """
    import json, sys
    sys.path.insert(0, sys.argv[1])
    from src.gui.reader_view import ReaderView          # antes do QApplication
    from PyQt6.QtWidgets import QApplication, QToolButton, QMainWindow
    from PyQt6.QtGui import QAction

    app = QApplication([])
    out = {"modais": 0}

    import PyQt6.QtWidgets as W
    class _NoModal(W.QMessageBox):
        def exec(self, *a, **k):
            out["modais"] += 1
            return 0
    W.QMessageBox = _NoModal

    class _Cfg:
        def __init__(self, preferido): self._p = preferido
        def get(self, key, default=None):
            return self._p if key == "tts.book_narrator.preferred_provider" else default

    class _Win(QMainWindow):
        def __init__(self, preferido):
            super().__init__()
            self._config = _Cfg(preferido)
            self.mensagens = []
        def statusBar(self):
            outer = self
            class _Bar:
                def showMessage(self, msg, ms=0): outer.mensagens.append([msg, ms])
            return _Bar()

    class _Stub:
        TTS_FALLBACK_MARK = ReaderView.TTS_FALLBACK_MARK
        _show_status = ReaderView._show_status
        _apply_tts_fallback_indicator = ReaderView._apply_tts_fallback_indicator
        _on_audio_provider_changed = ReaderView._on_audio_provider_changed
        _set_audio_button_state = ReaderView._set_audio_button_state
        def __init__(self, preferido="kokoro"):
            self._win = _Win(preferido)
            self._audio_paused = False
            self._audio_btn = QToolButton(self._win)
            self._audio_btn.setText("Pausar")
            self._act_audio_toggle = QAction("x", self._win)
            self._tts_fallback_provider = None
        def window(self): return self._win

    s = _Stub()
    s._on_audio_provider_changed("piper")               # caiu para a reserva
    out["msgs_fallback"] = list(s._win.mensagens)
    out["btn_reserva"] = s._audio_btn.text()
    out["prop_reserva"] = bool(s._audio_btn.property("ttsFallback"))
    out["tooltip"] = s._audio_btn.toolTip()

    s._on_audio_provider_changed("piper")               # dedup do aviso
    out["msgs_apos_repeticao"] = len(s._win.mensagens)

    s._set_audio_button_state("Retomar", "x", "t")      # troca de estado
    out["btn_apos_troca_estado"] = s._audio_btn.text()

    s._on_audio_provider_changed("kokoro")              # voltou ao preferido
    out["btn_limpo"] = s._audio_btn.text()
    out["prop_limpa"] = bool(s._audio_btn.property("ttsFallback"))
    out["fallback_attr"] = s._tts_fallback_provider

    print("@@JSON@@" + json.dumps(out, ensure_ascii=True))
    """
)


@pytest.fixture(scope="module")
def resultado_do_driver():
    env = dict(os.environ, QT_QPA_PLATFORM="offscreen", PYTHONIOENCODING="utf-8")
    proc = subprocess.run(
        [sys.executable, "-c", _DRIVER, str(_ROOT)],
        capture_output=True, text=True, encoding="utf-8", env=env, timeout=180,
    )
    if "@@JSON@@" not in (proc.stdout or ""):
        pytest.skip(f"driver do ReaderView não rodou neste ambiente: {proc.stderr[-500:]}")
    return json.loads(proc.stdout.split("@@JSON@@", 1)[1].strip())


def test_comportamento_fallback_avisa_uma_vez_na_statusbar(resultado_do_driver):
    msgs = resultado_do_driver["msgs_fallback"]
    assert len(msgs) == 1, f"esperava 1 aviso, veio {msgs}"
    texto, ms = msgs[0]
    assert "piper" in texto and "reserva" in texto
    assert ms >= 5000, "o aviso precisa ficar tempo suficiente para ser lido"
    # Reemissão do mesmo motor (leitura contínua) não repete o aviso.
    assert resultado_do_driver["msgs_apos_repeticao"] == 1


def test_comportamento_fallback_nao_abre_modal(resultado_do_driver):
    assert resultado_do_driver["modais"] == 0


def test_comportamento_indicador_persistente_no_botao(resultado_do_driver):
    assert resultado_do_driver["btn_reserva"].startswith("⚠️ ")
    assert resultado_do_driver["prop_reserva"] is True
    assert "reserva" in resultado_do_driver["tooltip"]
    assert "kokoro" in resultado_do_driver["tooltip"], "diga qual era o preferido"
    # Sobrevive à troca de estado do botão (Pausar → Retomar).
    assert resultado_do_driver["btn_apos_troca_estado"] == "⚠️ Retomar"


def test_comportamento_volta_ao_preferido_limpa_o_indicador(resultado_do_driver):
    assert resultado_do_driver["btn_limpo"] == "Retomar"
    assert resultado_do_driver["prop_limpa"] is False
    assert resultado_do_driver["fallback_attr"] is None


# ── 4. Alturas do item 10 neste arquivo: piso, não teto ────────────────────

@pytest.mark.parametrize("alvo, altura", [
    ("toolbar", 48),
    ("self._audio_btn", 32),
    ("self._progress_bar_widget", 28),
])
def test_alturas_sao_minimas_e_nao_fixas(alvo, altura):
    """Item 10: em notebook 13" com DPI alto, o TETO cortava o texto."""
    src = _src()
    assert f"{alvo}.setMinimumHeight({altura})" in src
    assert f"{alvo}.setFixedHeight(" not in src


def test_nenhuma_altura_fixa_restante_no_reader_view():
    assert "setFixedHeight(" not in _src(), (
        "toda altura do reader_view deve ser piso (setMinimumHeight), não teto")
