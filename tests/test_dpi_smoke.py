"""Fumaça de DPI/escala — item 10 do backlog do tester (rodada UX ago/2026).

O tester relatou, num notebook 13" com escala fracionária do Windows, que a
aba "🔊 Narração" das configurações SUMIA (10a) e que textos apareciam
cortados (10b).

Por que subprocesso: ``QT_SCALE_FACTOR``/``QT_FONT_DPI`` são lidos no boot do
Qt, então não dá para variá-los dentro do processo do pytest (que já tem um
QApplication). Mesmo padrão de ``tests/test_startup_deferred.py``.

Por que a fonte em PONTOS entra na conta: medido nesta suíte, na plataforma
``offscreen`` o ``QT_SCALE_FACTOR`` só mexe no devicePixelRatio — a DPI lógica
continua 96 e a geometria em px lógicos não muda. O que REALMENTE reproduz o
defeito do tester é a mistura de unidades: ``src/main.py`` define a fonte do
app em PONTOS e o QSS dimensiona em PIXELS, então quando a DPI sobe as letras
crescem e as caixas em px não. Os casos abaixo aplicam as duas coisas: a
escala pedida (documenta a intenção) e a fonte em pt equivalente a 125%/150%.
"""

import os
import subprocess
import sys
from pathlib import Path

import pytest

RAIZ = Path(__file__).resolve().parent.parent

# Roda o diálogo de configurações e imprime métricas em CHAVE=VALOR.
_FILHO = r'''
import os, sys, tempfile
from pathlib import Path

sys.path.insert(0, sys.argv[1])
FONT_PT = int(sys.argv[2])

from PyQt6.QtWidgets import (
    QAbstractSpinBox, QApplication, QComboBox, QWidget)
from PyQt6.QtGui import QFont

app = QApplication([])
app.setFont(QFont("Segoe UI", FONT_PT))  # como src/main.py: em PONTOS

from src.core.config import ConfigManager
from src.gui.settings_dialog import SettingsDialog
from src.gui.styles import get_theme

app.setStyleSheet(get_theme("dark"))  # o QSS em px é parte do problema

cfg = ConfigManager(Path(tempfile.mkdtemp()) / "config.json")
d = SettingsDialog(cfg)
d.resize(d.minimumSize())
d.show()
app.processEvents()

bar = d._tabs.tabBar()
print("ABAS=%s" % "|".join(bar.tabText(i) for i in range(bar.count())))
print("TABBAR_W=%d" % bar.width())
print("SOMA_ABAS=%d" % sum(bar.tabRect(i).width() for i in range(bar.count())))
print("SCROLL_BUTTONS=%s" % bar.usesScrollButtons())
print("ELIDE=%s" % bar.elideMode().name)
print("DIALOG_W=%d" % d.width())
print("DIALOG_H=%d" % d.height())

# (b) toda aba precisa virar corrente E ficar dentro da área visível do
#     tabBar; (c) nenhuma aba pode ter widget com texto cortado na vertical.
cortados = []
for i in range(bar.count()):
    d._tabs.setCurrentIndex(i)
    app.processEvents()
    r = bar.tabRect(i)
    print("ABA_%d_CORRENTE=%s" % (i, d._tabs.currentIndex() == i))
    print("ABA_%d_VISIVEL=%s" % (i, r.left() >= 0 and r.right() <= bar.width()))
    for w in d.findChildren(QWidget):
        if not w.isVisibleTo(d):
            continue
        if w.sizePolicy().verticalPolicy().name not in ("Fixed", "Minimum"):
            continue
        # Editor interno de combo/spin: quem manda na altura dele é o padding
        # do QSS do PAI, não o layout. Sair disso exigiria converter os 551
        # "font-size: px" do styles.py, que está fora do contrato desta onda.
        if isinstance(w.parent(), (QComboBox, QAbstractSpinBox)):
            continue
        if w.sizeHint().height() > w.height():
            cortados.append("aba%d:%s(%s) pai=%s h=%d hint=%d" % (
                i, type(w).__name__, w.objectName() or "-",
                type(w.parent()).__name__,
                w.height(), w.sizeHint().height()))
print("CORTADOS=%d" % len(cortados))
print("CORTADOS_DETALHE=%s" % " ; ".join(sorted(set(cortados))[:6]))

# caixas do item 10b: altura precisa acompanhar a fonte, não px cru
d._tabs.setCurrentIndex(5)
app.processEvents()
cmd = d._mcp_cmd_edit
fm = cmd.fontMetrics()
print("CMD_H=%d" % cmd.height())
print("CMD_LINHAS_NECESSARIAS=%d" % int(cmd.document().size().height()))
print("CMD_LINE_SPACING=%d" % fm.lineSpacing())
print("JSON_H=%d" % d._mcp_json_edit.height())

sys.stdout.flush()
sys.stderr.flush()
os._exit(0)
'''


def _metricas(scale: str, font_pt: int) -> dict[str, str]:
    """Roda o diálogo num Qt novo e devolve as métricas como dicionário."""
    env = dict(os.environ)
    env["QT_QPA_PLATFORM"] = "offscreen"
    env["PYTHONIOENCODING"] = "utf-8"
    env["QT_SCALE_FACTOR"] = scale
    proc = subprocess.run(
        [sys.executable, "-c", _FILHO, str(RAIZ), str(font_pt)],
        cwd=str(RAIZ), env=env, capture_output=True, text=True,
        encoding="utf-8", errors="replace", timeout=120,
    )
    dados = dict(
        linha.split("=", 1) for linha in proc.stdout.splitlines() if "=" in linha
    )
    assert "ABAS" in dados, (
        f"o subprocesso não reportou (rc={proc.returncode}).\n"
        f"stdout:\n{proc.stdout[-1500:]}\nstderr:\n{proc.stderr[-1500:]}")
    return dados


# 125% e 150%: a escala vai no ambiente e a fonte em pt equivale a 10pt × fator
@pytest.fixture(scope="module", params=[("1.25", 13), ("1.5", 15)],
                ids=["escala_125", "escala_150"])
def metricas(request):
    return _metricas(*request.param)


ABAS_ESPERADAS = ["Aparência", "Leitor", "Biblioteca", "Narração",
                  "Avançado", "Integrações"]


class TestAbasAlcancaveis:
    """10a: a aba do meio não pode sumir por overflow do QTabBar."""

    def test_as_seis_abas_existem(self, metricas):
        abas = metricas["ABAS"].split("|")
        assert len(abas) == 6, abas
        for esperada in ABAS_ESPERADAS:
            assert any(esperada in aba for aba in abas), (esperada, abas)

    def test_abas_cabem_no_tabbar_ou_tem_rolagem(self, metricas):
        soma = int(metricas["SOMA_ABAS"])
        largura = int(metricas["TABBAR_W"])
        assert soma <= largura or metricas["SCROLL_BUTTONS"] == "True", (
            f"abas somam {soma}px em {largura}px sem rolagem")

    def test_elide_ligado(self, metricas):
        # Com ElideNone o QTabBar não encolhe as abas: ele entra em modo
        # scroll e a aba corrente do meio sai da vista. Essa era a causa.
        assert metricas["ELIDE"] != "ElideNone"

    def test_toda_aba_vira_corrente_e_fica_visivel(self, metricas):
        for i in range(6):
            assert metricas[f"ABA_{i}_CORRENTE"] == "True", f"aba {i}"
            assert metricas[f"ABA_{i}_VISIVEL"] == "True", (
                f"aba {i} ficou fora da área visível do tabBar")

    def test_aba_narracao_alcancavel(self, metricas):
        indice = next(i for i, aba in enumerate(metricas["ABAS"].split("|"))
                      if "Narração" in aba)
        assert metricas[f"ABA_{indice}_CORRENTE"] == "True"
        assert metricas[f"ABA_{indice}_VISIVEL"] == "True"

    def test_dialogo_cabe_em_notebook_13(self, metricas):
        # 1366x768 lógicos a 125% ≈ 1092x614 úteis.
        assert int(metricas["DIALOG_W"]) <= 1092
        assert int(metricas["DIALOG_H"]) <= 614


class TestNadaCortadoNaVertical:
    """10b: nenhum widget de altura travada pode ficar menor que o texto."""

    def test_nenhum_widget_cortado(self, metricas):
        assert int(metricas["CORTADOS"]) == 0, metricas["CORTADOS_DETALHE"]

    def test_caixa_do_comando_mcp_cabe_o_texto(self, metricas):
        precisa = (int(metricas["CMD_LINHAS_NECESSARIAS"])
                   * int(metricas["CMD_LINE_SPACING"]))
        assert int(metricas["CMD_H"]) >= precisa, (
            f"comando MCP precisa de {precisa}px e a caixa tem "
            f"{metricas['CMD_H']}px")

    def test_alturas_acompanham_a_fonte(self, metricas):
        # Ancoradas no lineSpacing: 4 linhas na caixa do comando, 8 no JSON.
        espacamento = int(metricas["CMD_LINE_SPACING"])
        assert int(metricas["CMD_H"]) >= 4 * espacamento
        assert int(metricas["JSON_H"]) >= 8 * espacamento
