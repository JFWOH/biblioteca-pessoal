"""Medição de contraste WCAG dos 3 temas QSS do app (Onda S, rodada ago/2026).

Primeira medição do débito "acessibilidade nunca medida" (revisão de produto
2026-07-16 §7). Importa os temas prontos de ``src.gui.styles`` e, para cada
regra QSS que declara ``color`` E ``background-color`` no MESMO bloco, calcula
a razão de contraste WCAG 2.x (luminância relativa). Pares onde só uma das
duas cores aparece dependem do fundo herdado do pai — fora do alcance de uma
análise estática de QSS; ficam registrados como "ignorados".

Uso:
    venv\\Scripts\\python.exe tools/check_contrast.py --tema todos
    venv\\Scripts\\python.exe tools/check_contrast.py --tema dark --min-ratio 3.0
"""
from __future__ import annotations

import argparse
import re
import sys
from pathlib import Path

# Executável de qualquer cwd: garante a raiz do projeto no sys.path.
_RAIZ = Path(__file__).resolve().parent.parent
if str(_RAIZ) not in sys.path:
    sys.path.insert(0, str(_RAIZ))

_RE_REGRA = re.compile(r"([^{}]+)\{([^{}]*)\}", re.DOTALL)
_RE_HEX = re.compile(r"^#([0-9a-fA-F]{3}|[0-9a-fA-F]{6})$")
_RE_COMENTARIO = re.compile(r"/\*.*?\*/", re.DOTALL)


def _parse_hex(valor: str) -> tuple[int, int, int] | None:
    """Converte '#abc'/'#aabbcc' em (r, g, b); None para o que não for hex puro."""
    m = _RE_HEX.match(valor.strip())
    if not m:
        return None
    h = m.group(1)
    if len(h) == 3:
        h = "".join(c * 2 for c in h)
    return tuple(int(h[i:i + 2], 16) for i in (0, 2, 4))  # type: ignore[return-value]


def _luminancia(rgb: tuple[int, int, int]) -> float:
    """Luminância relativa WCAG (sRGB linearizado)."""
    def canal(c: int) -> float:
        s = c / 255.0
        return s / 12.92 if s <= 0.04045 else ((s + 0.055) / 1.055) ** 2.4

    r, g, b = (canal(c) for c in rgb)
    return 0.2126 * r + 0.7152 * g + 0.0722 * b


def razao_contraste(fg: tuple[int, int, int], bg: tuple[int, int, int]) -> float:
    """Razão de contraste WCAG: (L1 + 0.05) / (L2 + 0.05), L1 = mais clara."""
    l1, l2 = sorted((_luminancia(fg), _luminancia(bg)), reverse=True)
    return (l1 + 0.05) / (l2 + 0.05)


def classifica(ratio: float) -> str:
    if ratio >= 7.0:
        return "AAA"
    if ratio >= 4.5:
        return "AA"
    if ratio >= 3.0:
        return "AA-grande"
    return "FAIL"


def _declaracoes(corpo: str) -> dict[str, str]:
    """Extrai propriedade→valor do corpo de uma regra (última declaração vence)."""
    props: dict[str, str] = {}
    for linha in corpo.split(";"):
        if ":" not in linha:
            continue
        prop, _, valor = linha.partition(":")
        props[prop.strip().lower()] = valor.strip()
    return props


def analisa_tema(qss: str) -> tuple[list[tuple[str, str, str, float, str]], int]:
    """Devolve ([(seletor, fg, bg, ratio, classe), ...], ignorados).

    "Ignorados" = regras com os DOIS atributos, mas em formato não-hex
    (transparent, rgba(), gradiente, palette()) — sem como medir estaticamente.
    """
    pares: list[tuple[str, str, str, float, str]] = []
    ignorados = 0
    # O Qt descarta /* comentários */ do QSS; sem esta limpeza, um comentário
    # dentro da regra engoliria a declaração seguinte na partição por ";".
    qss = _RE_COMENTARIO.sub(" ", qss)
    for m in _RE_REGRA.finditer(qss):
        seletor = " ".join(m.group(1).split())
        props = _declaracoes(m.group(2))
        cor, fundo = props.get("color"), props.get("background-color")
        if not cor or not fundo:
            continue
        fg, bg = _parse_hex(cor), _parse_hex(fundo)
        if fg is None or bg is None:
            ignorados += 1
            continue
        ratio = razao_contraste(fg, bg)
        pares.append((seletor, cor, fundo, round(ratio, 2), classifica(ratio)))
    return pares, ignorados


def _temas_disponiveis() -> dict[str, str]:
    from src.gui.styles import DARK_THEME, LIGHT_THEME, SEPIA_THEME
    return {"dark": DARK_THEME, "light": LIGHT_THEME, "sepia": SEPIA_THEME}


def main(argv: list[str] | None = None) -> int:
    ap = argparse.ArgumentParser(description="Contraste WCAG dos temas QSS.")
    ap.add_argument("--tema", choices=["dark", "light", "sepia", "todos"],
                    default="todos")
    ap.add_argument("--min-ratio", type=float, default=None,
                    help="Só lista pares com razão ABAIXO deste valor.")
    args = ap.parse_args(argv)

    temas = _temas_disponiveis()
    nomes = list(temas) if args.tema == "todos" else [args.tema]

    for nome in nomes:
        pares, ignorados = analisa_tema(temas[nome])
        contagens = {"FAIL": 0, "AA-grande": 0, "AA": 0, "AAA": 0}
        for _, _, _, _, classe in pares:
            contagens[classe] += 1
        print(f"\n=== tema={nome} pares_medidos={len(pares)} "
              f"ignorados_nao_hex={ignorados} ===")
        print("resumo: " + "  ".join(f"{k}={v}" for k, v in contagens.items()))
        listar = [p for p in pares
                  if p[3] < (args.min_ratio if args.min_ratio is not None else 3.0)]
        rotulo = (f"abaixo de {args.min_ratio}" if args.min_ratio is not None
                  else "FAIL (<3:1)")
        print(f"pares {rotulo}: {len(listar)}")
        for seletor, fg, bg, ratio, classe in sorted(listar, key=lambda p: p[3]):
            print(f"  {ratio:>5.2f}  {classe:<9} {fg:>7} sobre {bg:>7}  {seletor}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
