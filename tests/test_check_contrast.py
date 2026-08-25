"""Testes da ferramenta de medição de contraste (tools/check_contrast.py)."""
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent / "tools"))

from check_contrast import (  # noqa: E402
    _parse_hex,
    analisa_tema,
    classifica,
    razao_contraste,
)


class TestFormulaWCAG:
    def test_preto_sobre_branco_e_21_para_1(self):
        assert razao_contraste((0, 0, 0), (255, 255, 255)) == 21.0

    def test_simetria(self):
        a, b = (18, 18, 18), (236, 236, 236)
        assert razao_contraste(a, b) == razao_contraste(b, a)

    def test_cinza_medio_conhecido(self):
        # #777777 sobre branco ≈ 4.48:1 (valor de referência WCAG conhecido).
        ratio = razao_contraste((0x77, 0x77, 0x77), (255, 255, 255))
        assert 4.4 < ratio < 4.6

    def test_classificacao(self):
        assert classifica(2.9) == "FAIL"
        assert classifica(3.0) == "AA-grande"
        assert classifica(4.5) == "AA"
        assert classifica(7.0) == "AAA"


class TestParser:
    def test_hex_curto_e_longo(self):
        assert _parse_hex("#fff") == (255, 255, 255)
        assert _parse_hex("#1a2b3c") == (0x1A, 0x2B, 0x3C)
        assert _parse_hex("transparent") is None
        assert _parse_hex("rgba(0,0,0,0.5)") is None

    def test_regra_com_par_completo(self):
        qss = """
        QLabel#titulo { color: #ffffff; background-color: #000000; padding: 4px; }
        QPushButton { color: #fff; }  /* sem fundo: fora da medição */
        """
        pares, ignorados = analisa_tema(qss)
        assert len(pares) == 1
        seletor, fg, bg, ratio, classe = pares[0]
        assert "QLabel#titulo" in seletor
        assert ratio == 21.0 and classe == "AAA"
        assert ignorados == 0

    def test_valor_nao_hex_conta_como_ignorado(self):
        qss = "QFrame { color: #fff; background-color: rgba(0,0,0,0.4); }"
        pares, ignorados = analisa_tema(qss)
        assert pares == [] and ignorados == 1

    def test_ultima_declaracao_vence(self):
        qss = "QLabel { color: #000; color: #fff; background-color: #000; }"
        pares, _ = analisa_tema(qss)
        assert pares[0][1] == "#fff"

    def test_comentario_nao_engole_declaracao(self):
        qss = ("QLabel { /* nota: 2,54:1 era FAIL */ color: #047857; "
               "background-color: #fff; }")
        pares, _ = analisa_tema(qss)
        assert len(pares) == 1 and pares[0][1] == "#047857"


class TestSmokeTemasReais:
    def test_encontra_pares_de_verdade_nos_3_temas(self):
        from src.gui.styles import DARK_THEME, LIGHT_THEME, SEPIA_THEME
        total = sum(len(analisa_tema(t)[0])
                    for t in (DARK_THEME, LIGHT_THEME, SEPIA_THEME))
        assert total > 50  # sanidade: o parser enxerga o QSS real
