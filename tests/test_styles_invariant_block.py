"""Rodada A3 (ciclo jul/2026-C) — guarda da consolidação do bloco invariante.

Contexto: ``src/gui/styles.py`` deixou de repetir, byte a byte, ~165 regras QSS
nos 3 temas. Essas regras (elementos estáticos do reader, badges/feedback/chips
do Assistente/RAG, ícones de estado, etc.) foram extraídas para uma única
constante ``_THEME_INVARIANT_QSS``, concatenada às 3 folhas na definição
(``DARK_THEME = _DARK_ONLY + _THEME_INVARIANT_QSS`` etc.).

Este teste é o guard-rail PERMANENTE pedido no contrato da rodada:

1. **Contagem de chaves balanceada** — cada folha final tem ``{`` == ``}``.
2. **Paridade dos invariantes entre os 3 temas** — todo seletor definido no
   bloco invariante resolve para declarações IDÊNTICAS nos 3 temas públicos.
   (Se alguém "corrigir" o bloco adicionando variante por tema, ou editar um
   tema quebrando a invariância, este teste falha.)
3. **Integridade da construção** — cada folha pública realmente termina com o
   bloco invariante (garante que a concatenação não foi desfeita).

Não depende de git nem do disco: opera só sobre as constantes importadas.
"""
import re

from src.gui.styles import (
    DARK_THEME,
    LIGHT_THEME,
    SEPIA_THEME,
    _THEME_INVARIANT_QSS,
)


def _parse_rules(qss: str):
    """QSS plano (sem aninhamento) -> lista de (selector_raw, body_raw).

    Ignora comentários ``/* */`` que aparecem nos intervalos entre regras.
    """
    rules = []
    i, n = 0, len(qss)
    while i < n:
        while i < n:
            if qss[i].isspace():
                i += 1
                continue
            if qss.startswith("/*", i):
                i = qss.index("*/", i) + 2
                continue
            break
        if i >= n:
            break
        sel_start = i
        while i < n and qss[i] != "{":
            if qss.startswith("/*", i):
                i = qss.index("*/", i) + 2
                continue
            i += 1
        if i >= n:
            break
        brace = i
        close = qss.index("}", brace)
        rules.append((qss[sel_start:brace], qss[brace + 1:close]))
        i = close + 1
    return rules


def _norm_decls(body: str) -> tuple:
    decls = []
    for chunk in body.split(";"):
        chunk = chunk.strip()
        if chunk and ":" in chunk:
            key, val = chunk.split(":", 1)
            decls.append(
                (re.sub(r"\s+", " ", key).strip(), re.sub(r"\s+", " ", val).strip())
            )
    return tuple(decls)


def _expanded_map(qss: str) -> dict:
    """{seletor individual -> declarações normalizadas} (last-wins = cascata)."""
    out = {}
    for sel_raw, body in _parse_rules(qss):
        decls = _norm_decls(body)
        sel = re.sub(r"/\*.*?\*/", "", sel_raw, flags=re.DOTALL)
        sel = re.sub(r"\s+", " ", sel).strip()
        for part in (p.strip() for p in sel.split(",")):
            if part:
                out[part] = decls
    return out


ALL_THEMES = {"dark": DARK_THEME, "light": LIGHT_THEME, "sepia": SEPIA_THEME}


def test_all_themes_have_balanced_braces():
    for name, css in ALL_THEMES.items():
        assert css.count("{") == css.count("}"), (
            f"{name}: chaves desbalanceadas ({css.count('{')} != {css.count('}')})"
        )


def test_each_theme_ends_with_invariant_block():
    # a construção é _X_ONLY + _THEME_INVARIANT_QSS: o bloco é sufixo literal.
    for name, css in ALL_THEMES.items():
        assert css.endswith(_THEME_INVARIANT_QSS), (
            f"{name}: não termina com _THEME_INVARIANT_QSS (concatenação desfeita?)"
        )


def test_invariant_block_is_substantial():
    # rede de segurança contra esvaziamento acidental do bloco.
    inv = _expanded_map(_THEME_INVARIANT_QSS)
    assert len(inv) >= 150, f"bloco invariante inesperadamente pequeno: {len(inv)}"


def test_invariant_selectors_are_byte_identical_across_the_three_themes():
    """Todo seletor do bloco invariante tem declarações idênticas nos 3 temas."""
    inv = _expanded_map(_THEME_INVARIANT_QSS)
    md = _expanded_map(DARK_THEME)
    ml = _expanded_map(LIGHT_THEME)
    ms = _expanded_map(SEPIA_THEME)
    divergences = []
    for sel in inv:
        vals = {"dark": md.get(sel), "light": ml.get(sel), "sepia": ms.get(sel)}
        if not (vals["dark"] == vals["light"] == vals["sepia"]):
            divergences.append((sel, vals))
    assert not divergences, (
        "seletores do bloco invariante divergem entre temas: "
        + "; ".join(sel for sel, _ in divergences[:8])
    )


def test_three_themes_share_the_same_selector_universe():
    """Paridade estrutural: os 3 temas definem exatamente os mesmos seletores."""
    dark = set(_expanded_map(DARK_THEME))
    light = set(_expanded_map(LIGHT_THEME))
    sepia = set(_expanded_map(SEPIA_THEME))
    assert dark == light == sepia, (
        "universo de seletores difere entre temas: "
        f"D\\L={sorted(dark - light)[:5]} L\\S={sorted(light - sepia)[:5]}"
    )
