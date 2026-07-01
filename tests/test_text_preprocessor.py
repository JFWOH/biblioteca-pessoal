"""
Tests for the Phase 13 TTS Text Preprocessor.

Validates all preprocessing transformations:
- OCR artifact cleanup
- Reference marker removal
- Dialogue normalization
- Quote handling
- List conversion
- Abbreviation expansion
- Number normalization
- Punctuation handling
- Prosodic pause insertion
"""

import pytest
from src.core.tts.text_preprocessor import TTSTextPreprocessor


@pytest.fixture
def preprocessor():
    return TTSTextPreprocessor(language="pt-BR")


@pytest.fixture
def preprocessor_en():
    return TTSTextPreprocessor(language="en-US")


# ── OCR Artifact Cleanup ─────────────────────────────────────────────

class TestOCRArtifacts:
    def test_removes_isolated_page_numbers(self, preprocessor):
        text = "Texto normal.\n\n42\n\nMais texto."
        result = preprocessor.clean_ocr_artifacts(text)
        assert "42" not in result
        assert "Texto normal." in result
        assert "Mais texto." in result

    def test_removes_pdf_hyphenation(self, preprocessor):
        text = "com-\nputador"
        result = preprocessor.clean_ocr_artifacts(text)
        assert "computador" in result

    def test_normalizes_excessive_dots(self, preprocessor):
        text = "texto........mais texto"
        result = preprocessor.clean_ocr_artifacts(text)
        assert "…" in result
        assert "........" not in result

    def test_removes_control_characters(self, preprocessor):
        text = "texto\x00normal\x01aqui"
        result = preprocessor.clean_ocr_artifacts(text)
        assert "\x00" not in result
        assert "\x01" not in result

    def test_removes_pipe_characters(self, preprocessor):
        text = "coluna1 | coluna2 | coluna3"
        result = preprocessor.clean_ocr_artifacts(text)
        assert "|" not in result


# ── Reference Markers ────────────────────────────────────────────────

class TestReferenceMarkers:
    def test_removes_superscript_after_period(self, preprocessor):
        result = preprocessor.clean_reference_markers("importantes.² Enriquecer")
        assert result == "importantes. Enriquecer"

    def test_removes_html_sup(self, preprocessor):
        result = preprocessor.clean_reference_markers("texto<sup>2</sup> continua")
        assert "<sup>" not in result
        assert "texto continua" in result

    def test_removes_bracket_references(self, preprocessor):
        result = preprocessor.clean_reference_markers("texto.[2] Próximo")
        assert "[2]" not in result
        assert "texto. Próximo" in result

    def test_preserves_square_meter(self, preprocessor):
        result = preprocessor.clean_reference_markers("15 m² de área")
        assert "m²" in result

    def test_preserves_mc_squared(self, preprocessor):
        result = preprocessor.clean_reference_markers("E=mc² é famosa")
        assert "mc²" in result


# ── Dialogue Normalization ───────────────────────────────────────────

class TestDialogueNormalization:
    def test_removes_em_dash_at_line_start(self, preprocessor):
        text = "— Bom dia, disse João."
        result = preprocessor.normalize_dialogues(text)
        assert result.strip() == "Bom dia, disse João."
        assert "—" not in result

    def test_converts_inline_em_dash_to_comma(self, preprocessor):
        text = "disse ele — com voz firme."
        result = preprocessor.normalize_dialogues(text)
        assert "—" not in result
        assert "," in result

    def test_handles_double_dash(self, preprocessor):
        text = "algo -- muito importante"
        result = preprocessor.normalize_dialogues(text)
        assert "--" not in result


# ── Quote Normalization ──────────────────────────────────────────────

class TestQuoteNormalization:
    def test_removes_fancy_quotes(self, preprocessor):
        text = '"texto citado" e mais'
        result = preprocessor.normalize_quotes(text)
        assert "\u201c" not in result
        assert "\u201d" not in result

    def test_removes_quotation_marks_for_speech(self, preprocessor):
        text = '"texto citado" continua'
        result = preprocessor.normalize_quotes(text)
        assert '"' not in result
        assert "texto citado" in result


# ── List Normalization ───────────────────────────────────────────────

class TestListNormalization:
    def test_removes_bullet_points(self, preprocessor):
        text = "• Item um\n• Item dois"
        result = preprocessor.normalize_lists(text)
        assert "•" not in result
        assert "Item um" in result

    def test_removes_numbered_list_markers(self, preprocessor):
        text = "1. Primeiro\n2. Segundo"
        result = preprocessor.normalize_lists(text)
        assert "1." not in result
        assert "Primeiro" in result

    def test_removes_letter_list_markers(self, preprocessor):
        text = "a) Alpha\nb) Beta"
        result = preprocessor.normalize_lists(text)
        assert "a)" not in result
        assert "Alpha" in result


# ── Abbreviation Expansion ───────────────────────────────────────────

class TestAbbreviationExpansion:
    def test_expands_dr(self, preprocessor):
        result = preprocessor.expand_abbreviations("Dr. Silva chegou")
        assert "Doutor" in result
        assert "Dr." not in result

    def test_expands_sr(self, preprocessor):
        result = preprocessor.expand_abbreviations("Sr. João falou")
        assert "Senhor" in result

    def test_expands_etc(self, preprocessor):
        result = preprocessor.expand_abbreviations("livros, cadernos, etc. tudo")
        assert "etcétera" in result

    def test_expands_english_abbreviations(self, preprocessor_en):
        result = preprocessor_en.expand_abbreviations("e.g. this is an example")
        assert "for example" in result

    def test_expands_pag(self, preprocessor):
        result = preprocessor.expand_abbreviations("ver pág. 42")
        assert "página" in result


# ── Number Normalization ─────────────────────────────────────────────

class TestNumberNormalization:
    def test_expands_ordinals_pt(self, preprocessor):
        result = preprocessor.normalize_numbers("1º lugar")
        assert "primeiro" in result

    def test_expands_female_ordinals_pt(self, preprocessor):
        result = preprocessor.normalize_numbers("2ª edição")
        assert "segunda" in result

    def test_expands_percentage_pt(self, preprocessor):
        result = preprocessor.normalize_numbers("50% dos casos")
        assert "50 por cento" in result

    def test_expands_currency_pt(self, preprocessor):
        result = preprocessor.normalize_numbers("R$ 100 de custo")
        assert "100 reais" in result
        assert "R$" not in result

    def test_expands_section_symbol_pt(self, preprocessor):
        result = preprocessor.normalize_numbers("§ único")
        assert "parágrafo" in result

    def test_expands_percentage_en(self, preprocessor_en):
        result = preprocessor_en.normalize_numbers("50% of cases")
        assert "50 percent" in result


# ── Punctuation Normalization ────────────────────────────────────────

class TestPunctuationNormalization:
    def test_reduces_multiple_exclamation(self, preprocessor):
        result = preprocessor.normalize_punctuation("Incrível!!!")
        assert result == "Incrível!"

    def test_reduces_multiple_question(self, preprocessor):
        result = preprocessor.normalize_punctuation("O quê???")
        assert result == "O quê?"

    def test_semicolon_to_comma(self, preprocessor):
        result = preprocessor.normalize_punctuation("item; outro")
        assert ";" not in result
        assert "," in result

    def test_removes_parentheses_keeps_content(self, preprocessor):
        result = preprocessor.normalize_punctuation("algo (importante) aqui")
        assert "(" not in result
        assert ")" not in result
        assert "importante" in result


# ── Full Pipeline ────────────────────────────────────────────────────

class TestFullPipeline:
    def test_empty_text_returns_empty(self, preprocessor):
        assert preprocessor.prepare_for_speech("") == ""
        assert preprocessor.prepare_for_speech("   ") == ""

    def test_simple_text_passes_through(self, preprocessor):
        result = preprocessor.prepare_for_speech("Texto simples e limpo.")
        assert "Texto simples e limpo." in result

    def test_complex_text_is_improved(self, preprocessor):
        raw = """— Bom dia, Dr. Silva! — disse João.
O valor era de R$ 100, ou seja, 50% do total.
Ver pág. 42 para mais detalhes etc.
A sala tem 15 m² de área."""
        result = preprocessor.prepare_for_speech(raw, style="serene")
        # Dialogues should be cleaned
        assert "—" not in result
        # Abbreviations expanded
        assert "Doutor" in result
        assert "etcétera" in result
        assert "página" in result
        # Numbers normalized
        assert "100 reais" in result
        assert "50 por cento" in result
        # Math preserved
        assert "m²" in result

    def test_ocr_dirty_text_is_cleaned(self, preprocessor):
        raw = "com-\nputador era muito bom.\n\n42\n\nE a vida continua........"
        result = preprocessor.prepare_for_speech(raw)
        assert "computador" in result
        assert "42" not in result.split("E a vida")[0]  # Page number removed

    def test_preserve_style_parameter(self, preprocessor):
        text = "Parágrafo um.\n\nParágrafo dois."
        serene = preprocessor.prepare_for_speech(text, style="serene")
        didactic = preprocessor.prepare_for_speech(text, style="didactic")
        # Both should produce valid output
        assert "Parágrafo um." in serene
        assert "Parágrafo dois." in didactic


# ── Architectural Compliance ─────────────────────────────────────────

class TestArchitecturalCompliance:
    def test_tts_module_does_not_import_pyqt6(self):
        """ADR-006: Core TTS code must not import PyQt6."""
        import ast
        import os

        tts_dir = os.path.join("src", "core", "tts")
        if not os.path.isdir(tts_dir):
            pytest.skip("TTS directory not found")

        for root, _, files in os.walk(tts_dir):
            for file in files:
                if file.endswith(".py"):
                    filepath = os.path.join(root, file)
                    with open(filepath, "r", encoding="utf-8") as f:
                        tree = ast.parse(f.read(), filename=filepath)
                        for node in ast.walk(tree):
                            if isinstance(node, ast.Import):
                                for alias in node.names:
                                    assert "PyQt6" not in alias.name, \
                                        f"PyQt6 import in {filepath}"
                            elif isinstance(node, ast.ImportFrom):
                                if node.module:
                                    assert "PyQt6" not in node.module, \
                                        f"PyQt6 import in {filepath}"
