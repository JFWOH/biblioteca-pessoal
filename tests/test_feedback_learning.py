"""Testes da lógica pura de aprendizado por feedback (src/core/feedback_learning).

Cobre os limiares (≥2 negativos, categoria ≥2, teto de 2 — ajustados de 4/3
para 2/2 na tarefa 3.8, feedback acionável), o desempate canônico, texto
livre que não vira categoria, robustez a linhas malformadas (ADR-005) e a
garantia de núcleo puro (ADR-006: sem PyQt6).
"""

from __future__ import annotations

import ast
from pathlib import Path

from src.core.feedback_learning import build_feedback_block

# Fragmentos distintivos de cada instrução canônica (pegam regressões de texto).
_FRAG_ERRADA = "Verifique cada afirmação"
_FRAG_INCOMPLETA = "respostas completas"
_FRAG_FORA = "Restrinja-se ao conteúdo do livro atual"
_FRAG_GENERICA = "Evite respostas genéricas"
_FRAG_GENERIC_BULLET = "Capriche na fundamentação"
_FRAG_HEADER = "avaliou negativamente"


def _neg(reason: str = "") -> dict:
    return {"rating": -1, "reason": reason}


def _pos(reason: str = "") -> dict:
    return {"rating": 1, "reason": reason}


class TestBuildFeedbackBlock:
    def test_returns_none_below_two_negatives(self):
        rows = [_neg("resposta_errada")] + [_pos()]
        assert build_feedback_block(rows) is None

    def test_empty_rows_return_none(self):
        assert build_feedback_block([]) is None

    def test_generic_block_when_no_category_qualifies(self):
        # 2 negativos, mas nenhum motivo canônico com ≥2 ocorrências (motivos
        # distintos, 1 hit cada).
        rows = [_neg("resposta_errada"), _neg("incompleta")]
        block = build_feedback_block(rows)
        assert block is not None
        assert _FRAG_HEADER in block
        assert _FRAG_GENERIC_BULLET in block
        # Bullet genérico único: nenhuma instrução de categoria aparece.
        assert _FRAG_ERRADA not in block
        assert block.count("\n- ") == 1

    def test_category_with_two_hits_qualifies(self):
        rows = [_neg("resposta_errada") for _ in range(2)]
        block = build_feedback_block(rows)
        assert block is not None
        assert _FRAG_ERRADA in block
        assert _FRAG_GENERIC_BULLET not in block

    def test_ceiling_of_two_categories_by_count(self):
        # Contagens distintas (todas ≥2, já qualificam): as duas maiores
        # entram; a terceira fica de fora mesmo qualificando.
        rows = ([_neg("generica") for _ in range(4)]
                + [_neg("fora_contexto") for _ in range(3)]
                + [_neg("resposta_errada") for _ in range(2)])
        block = build_feedback_block(rows)
        assert block is not None
        assert _FRAG_GENERICA in block
        assert _FRAG_FORA in block
        assert _FRAG_ERRADA not in block
        assert block.count("\n- ") == 2

    def test_tiebreak_follows_canonical_order(self):
        # Empate de contagem (2 cada): desempate pela ordem canônica
        # resposta_errada > incompleta > fora_contexto.
        rows = ([_neg("resposta_errada") for _ in range(2)]
                + [_neg("incompleta") for _ in range(2)]
                + [_neg("fora_contexto") for _ in range(2)])
        block = build_feedback_block(rows)
        assert block is not None
        assert _FRAG_ERRADA in block
        assert _FRAG_INCOMPLETA in block
        assert _FRAG_FORA not in block

    def test_free_text_does_not_become_category(self):
        # 2 negativos com texto livre "Outro…" — conta como negativo, mas
        # nenhuma categoria canônica qualifica → bloco genérico.
        rows = [_neg("Outro: a resposta inventou uma citação") for _ in range(2)]
        block = build_feedback_block(rows)
        assert block is not None
        assert _FRAG_GENERIC_BULLET in block
        assert _FRAG_ERRADA not in block

    def test_free_text_counts_toward_negatives_total(self):
        # 2 resposta_errada (já qualifica sozinha) + 1 texto livre = 3
        # negativos no total; o texto livre soma ao total mas não vira categoria.
        rows = ([_neg("resposta_errada") for _ in range(2)]
                + [_neg("comentário livre qualquer")])
        block = build_feedback_block(rows)
        assert block is not None
        assert _FRAG_ERRADA in block

    def test_positive_ratings_are_not_negatives(self):
        rows = [_pos("resposta_errada") for _ in range(10)]
        assert build_feedback_block(rows) is None

    def test_malformed_rows_are_ignored(self):
        rows = [
            "não é dict",
            {"reason": "resposta_errada"},        # sem rating
            {"rating": "ruim", "reason": "x"},     # rating não numérico
            {"rating": None},                       # rating None
            {"rating": True, "reason": "y"},        # bool não é nota
            {"rating": -1, "reason": "resposta_errada"},
        ]
        # Apenas 1 negativo válido → sem sinal suficiente (< 2), sem exceção.
        assert build_feedback_block(rows) is None

    def test_reason_is_stripped_before_matching(self):
        rows = [_neg("  resposta_errada  ") for _ in range(2)]
        block = build_feedback_block(rows)
        assert block is not None
        assert _FRAG_ERRADA in block


class TestCorePurity:
    def test_module_does_not_import_pyqt6(self):
        """ADR-006: o núcleo não pode importar PyQt6/PySide (nem indiretamente
        via import estático). Inspeciona a AST do módulo."""
        src = Path("src/core/feedback_learning.py").read_text(encoding="utf-8")
        tree = ast.parse(src)
        imported: list[str] = []
        for node in ast.walk(tree):
            if isinstance(node, ast.Import):
                imported.extend(alias.name for alias in node.names)
            elif isinstance(node, ast.ImportFrom) and node.module:
                imported.append(node.module)
        forbidden = [m for m in imported
                     if m.startswith("PyQt") or m.startswith("PySide")]
        assert forbidden == [], f"imports proibidos no core: {forbidden}"
