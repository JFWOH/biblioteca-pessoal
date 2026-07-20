"""Fronteira da API pública do TTSRouter (débito 3.6, rodada B2).

A GUI não pode acessar membros PRIVADOS do router — a síntese-sem-tocar é
API pública (``synthesize_segments``). Guarda estrutural por varredura de
fonte (mesmo padrão dos testes de wiring do reader_view).
"""
import re
from pathlib import Path

_GUI = Path(__file__).resolve().parent.parent / "src" / "gui"

# Acessos proibidos: atributo privado logo após uma referência a router
# (``router._x`` / ``self._router._x``) ou privado de classe
# (``TTSRouter._x``). O próprio atributo ``self._router`` é permitido.
_FORBIDDEN = re.compile(r"(?:\brouter\.|_router\.|TTSRouter\.)_[a-z]")


def test_gui_nao_acessa_privados_do_tts_router():
    offenders = []
    for py in _GUI.rglob("*.py"):
        src = py.read_text(encoding="utf-8")
        for n, line in enumerate(src.splitlines(), 1):
            if _FORBIDDEN.search(line):
                offenders.append(f"{py.name}:{n}: {line.strip()}")
    assert offenders == [], (
        "GUI acessando privados do TTSRouter (use a API pública, ex. "
        "synthesize_segments):\n" + "\n".join(offenders))


def test_synthesize_segments_e_publica_e_documentada():
    router_src = (_GUI.parent / "core" / "tts" / "tts_router.py").read_text(
        encoding="utf-8")
    assert "def synthesize_segments(self, text: str, role: NarrationRole" in router_src
    # Contrato de paralelismo: o método não pode escrever no estado de
    # reprodução do speak() (leitura de fonte: nenhuma atribuição).
    m = re.search(r"def synthesize_segments\(.*?\n(.*?)\n    def ",
                  router_src, re.DOTALL)
    assert m, "corpo de synthesize_segments não encontrado"
    body = m.group(1)
    assert "_is_cancelled =" not in body
    assert "_active_player =" not in body
