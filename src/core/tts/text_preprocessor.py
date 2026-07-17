"""
TTS Text Preprocessor — Enhanced text preparation for speech synthesis.

Goes beyond the original text_chunker.py cleaning by adding:
- Dialogue/dash handling for Brazilian Portuguese
- Quote normalization
- List/enumeration handling
- Number expansion for natural speech
- Complex punctuation normalization
- Abbreviation expansion
- OCR artifact cleanup
- Visual noise removal

This is the mandatory preprocessing layer required by Phase 13.

ADR-006 compliance: No PyQt6 imports.
"""

import re
import logging

from src.core.tts.text_preprocess import mark_heading_pauses

logger = logging.getLogger(__name__)


class TTSTextPreprocessor:
    """Pre-processes text for optimal TTS synthesis quality.

    Each method handles a specific class of text artifacts.
    The main entry point is `prepare_for_speech()` which applies
    all transformations in the correct order.
    """

    # Common PT-BR abbreviations → expansions for TTS
    ABBREVIATIONS_PT = {
        r'\bDr\.': 'Doutor',
        r'\bDra\.': 'Doutora',
        r'\bSr\.': 'Senhor',
        r'\bSra\.': 'Senhora',
        r'\bSrta\.': 'Senhorita',
        r'\bProf\.': 'Professor',
        r'\bProfa\.': 'Professora',
        r'\bEng\.': 'Engenheiro',
        r'\bAdv\.': 'Advogado',
        r'\bEx\.': 'Exemplo',
        r'\bP\.ex\.': 'Por exemplo',
        r'\bp\.ex\.': 'por exemplo',
        r'\betc\.': 'etcétera',
        r'\bvs\.': 'versus',
        r'\bVS\.': 'versus',
        r'\bpág\.': 'página',
        r'\bPág\.': 'Página',
        r'\bfig\.': 'figura',
        r'\bFig\.': 'Figura',
        r'\bcap\.': 'capítulo',
        r'\bCap\.': 'Capítulo',
        r'\bEd\.': 'Edição',
        r'\bed\.': 'edição',
        r'\bVol\.': 'Volume',
        r'\bvol\.': 'volume',
        r'\bN\.º': 'Número',
        r'\bn\.º': 'número',
        r'\bnº': 'número',
        r'\bNº': 'Número',
    }

    # Common EN abbreviations
    ABBREVIATIONS_EN = {
        r'\bDr\.': 'Doctor',
        r'\bMr\.': 'Mister',
        r'\bMrs\.': 'Missus',
        r'\bMs\.': 'Miss',
        r'\bProf\.': 'Professor',
        r'\betc\.': 'etcetera',
        r'\bvs\.': 'versus',
        r'\bFig\.': 'Figure',
        r'\bfig\.': 'figure',
        r'\bVol\.': 'Volume',
        r'\bvol\.': 'volume',
        r'\bCh\.': 'Chapter',
        r'\bch\.': 'chapter',
        r'\be\.g\.': 'for example',
        r'\bi\.e\.': 'that is',
    }

    def __init__(self, language: str = "pt-BR"):
        self._language = language
        self._abbreviations = (
            self.ABBREVIATIONS_PT if language.startswith("pt")
            else self.ABBREVIATIONS_EN
        )

    # ── Main Entry Point ──────────────────────────────────────────────

    def prepare_for_speech(self, text: str,
                           style: str = "serene") -> str:
        """Apply all preprocessing transformations to raw text.

        Args:
            text: Raw text from PDF/EPUB/reader extraction.
            style: Narration style hint ('serene', 'technical', 'didactic').
                   Affects pause insertion intensity.

        Returns:
            Cleaned text optimized for TTS synthesis.
        """
        if not text or not text.strip():
            return ""

        result = text

        # 1. Remove OCR artifacts and visual noise
        result = self.clean_ocr_artifacts(result)

        # 2. Remove reference markers (reuse existing logic)
        result = self.clean_reference_markers(result)

        # 2.5 Marca pausa em títulos/subtítulos (linhas curtas isoladas por
        # quebras) para que a síntese não os cole na frase seguinte (sintoma
        # "...a vida real. companheirismo Harold e Erica..."). PRECISA rodar
        # ANTES de normalize_whitespace, que colapsa as quebras simples.
        result = mark_heading_pauses(result)

        # 3. Normalize whitespace and line breaks
        result = self.normalize_whitespace(result)

        # 4. Handle dialogues (em-dashes, quotation marks)
        result = self.normalize_dialogues(result)

        # 5. Normalize quotes
        result = self.normalize_quotes(result)

        # 6. Handle lists and enumerations
        result = self.normalize_lists(result)

        # 7. Expand abbreviations
        result = self.expand_abbreviations(result)

        # 8. Normalize numbers for speech
        result = self.normalize_numbers(result)

        # 9. Normalize complex punctuation
        result = self.normalize_punctuation(result)

        # 10. Insert prosodic pauses based on style
        result = self.insert_pauses(result, style)

        # 11. Final whitespace cleanup
        result = re.sub(r' {2,}', ' ', result).strip()

        return result

    # ── Individual Transformations ────────────────────────────────────

    def clean_ocr_artifacts(self, text: str) -> str:
        """Remove common OCR extraction artifacts."""
        if not text:
            return ""

        # Remove page numbers isolated on their own line
        text = re.sub(r'^\s*\d{1,4}\s*$', '', text, flags=re.MULTILINE)

        # Remove header/footer repeated patterns (short lines that look like headers)
        text = re.sub(r'^\s*[A-ZÁÉÍÓÚÀÂÊÔÃÕÇ\s]{3,50}\s*$', '', text,
                      flags=re.MULTILINE, count=2)

        # Remove PDF line-break hyphens: 'com-\nputador' → 'computador'
        text = re.sub(r'(?<=\w)-\s*\n\s*(?=\w)', '', text)

        # Remove isolated control characters
        text = re.sub(r'[\x00-\x08\x0b\x0c\x0e-\x1f]', '', text)

        # Remove excessive dots (...... → …)
        text = re.sub(r'\.{4,}', '…', text)

        # Remove standalone pipe/bar characters often from OCR tables
        text = re.sub(r'\s*\|\s*', ' ', text)

        return text

    def clean_reference_markers(self, text: str) -> str:
        """Remove footnote/reference markers that are noise for TTS.

        Reuses and extends the logic from text_chunker.py while being
        compatible with the existing clean_reference_markers_for_tts function.
        """
        if not text:
            return ""

        # Protect math expressions (m², mc², etc.)
        protected = {}
        def protect(match):
            placeholder = f"__MATH_{len(protected)}__"
            protected[placeholder] = match.group(0)
            return placeholder

        unit_pattern = r'(?i)\b(m|cm|km|mm|dm|x|y|z|a|b|c|mc)[²³]\b'
        text = re.sub(unit_pattern, protect, text)

        # Remove HTML <sup> reference tags
        text = re.sub(r'<sup\b[^>]*>.*?</sup>', '', text, flags=re.IGNORECASE)

        # Remove superscript digits after punctuation
        text = re.sub(r'(?<!\d)([.!?;:,])\s*[¹²³⁴⁵⁶⁷⁸⁹⁰]+(?=\s|$)', r'\1', text)

        # Remove ASCII digit references after punctuation followed by uppercase
        text = re.sub(r'(?<!\d)([.!?;:,])\s*\d{1,3}(?=\s+[A-ZÀ-Ú]|\s*$)', r'\1', text)

        # Remove superscript digits before punctuation
        text = re.sub(r'(?<=\w)[¹²³⁴⁵⁶⁷⁸⁹⁰]+(?=[.!?;:,])', '', text)

        # Remove bracketed references after punctuation
        text = re.sub(r'(?<!\d)([.!?;:,])(\s*\[\d{1,4}\])+(?=\s|$)', r'\1', text)

        # Restore protected math expressions
        for placeholder, original in protected.items():
            text = text.replace(placeholder, original)

        return text

    def normalize_whitespace(self, text: str) -> str:
        """Normalize line breaks and spacing for coherent speech."""
        if not text:
            return ""

        # Preserve paragraph breaks (double newline) as sentence boundaries
        paragraphs = text.split("\n\n")
        cleaned = []

        for p in paragraphs:
            # Single newlines within paragraph → space
            p_clean = p.replace("\n", " ")
            # Collapse multiple spaces
            p_clean = re.sub(r' {2,}', ' ', p_clean).strip()
            if p_clean:
                cleaned.append(p_clean)

        return "\n\n".join(cleaned)

    def normalize_dialogues(self, text: str) -> str:
        """Handle Brazilian Portuguese dialogue conventions for TTS.

        PT-BR dialogues use em-dash (—) or double dash (--) to mark
        speech. These should be converted to natural pause markers.
        """
        if not text:
            return ""

        # Em-dash at start of line/paragraph = dialogue marker
        # Replace with a natural pause indicator
        text = re.sub(r'^\s*[—–]\s*', '', text, flags=re.MULTILINE)

        # Em-dash used as speech attribution within dialogue
        # '...disse ele — com voz firme.' → '...disse ele, com voz firme.'
        text = re.sub(r'\s+[—–]\s+', ', ', text)

        # Double dash as em-dash substitute
        text = re.sub(r'\s*--\s*', ', ', text)

        return text

    def normalize_quotes(self, text: str) -> str:
        """Normalize quotation marks for cleaner TTS output."""
        if not text:
            return ""

        # Replace fancy quotes with standard ones (TTS handles them better)
        text = text.replace('\u201c', '"')  # "
        text = text.replace('\u201d', '"')  # "
        text = text.replace('\u2018', "'")  # '
        text = text.replace('\u2019', "'")  # '
        text = text.replace('\u00ab', '"')  # «
        text = text.replace('\u00bb', '"')  # »

        # Remove quotes entirely for cleaner speech (the voice should convey tone)
        text = re.sub(r'"([^"]*)"', r'\1', text)

        return text

    def normalize_lists(self, text: str) -> str:
        """Convert visual list markers to speech-friendly format."""
        if not text:
            return ""

        # Bullet points → natural enumeration
        text = re.sub(r'^\s*[•●◦▪▸►]\s*', '', text, flags=re.MULTILINE)

        # Numbered lists: '1. Item' → 'Item' (number is visual, not speech)
        # Only when at start of line
        text = re.sub(r'^\s*\d{1,3}[.)]\s+', '', text, flags=re.MULTILINE)

        # Letter lists: 'a) Item' → 'Item'
        text = re.sub(r'^\s*[a-zA-Z][.)]\s+', '', text, flags=re.MULTILINE)

        # Roman numeral lists: 'i) Item', 'ii. Item'
        text = re.sub(r'^\s*[ivxlcdm]+[.)]\s+', '', text,
                      flags=re.MULTILINE | re.IGNORECASE)

        return text

    def expand_abbreviations(self, text: str) -> str:
        """Expand common abbreviations to full words for natural speech."""
        if not text:
            return ""

        for pattern, replacement in self._abbreviations.items():
            text = re.sub(pattern, replacement, text)

        return text

    def normalize_numbers(self, text: str) -> str:
        """Make numbers more natural for speech.

        Handles ordinals, decimals, percentages, etc.
        Full number-to-words expansion is left to the TTS engine.
        """
        if not text:
            return ""

        # Ordinals: 1º → primeiro, 2ª → segunda (basic PT-BR)
        if self._language.startswith("pt"):
            ordinals_m = {
                '1º': 'primeiro', '2º': 'segundo', '3º': 'terceiro',
                '4º': 'quarto', '5º': 'quinto', '6º': 'sexto',
                '7º': 'sétimo', '8º': 'oitavo', '9º': 'nono',
                '10º': 'décimo',
            }
            ordinals_f = {
                '1ª': 'primeira', '2ª': 'segunda', '3ª': 'terceira',
                '4ª': 'quarta', '5ª': 'quinta', '6ª': 'sexta',
                '7ª': 'sétima', '8ª': 'oitava', '9ª': 'nona',
                '10ª': 'décima',
            }
            for short, full in {**ordinals_m, **ordinals_f}.items():
                text = text.replace(short, full)

        # Percentage: '50%' → '50 por cento' / '50 percent'
        if self._language.startswith("pt"):
            text = re.sub(r'(\d+(?:[.,]\d+)?)\s*%', r'\1 por cento', text)
        else:
            text = re.sub(r'(\d+(?:[.,]\d+)?)\s*%', r'\1 percent', text)

        # Currency: 'R$ 100' → '100 reais' (basic)
        if self._language.startswith("pt"):
            text = re.sub(r'R\$\s*(\d+(?:[.,]\d+)?)', r'\1 reais', text)

        # Section symbol: '§' → 'parágrafo' / 'section'
        if self._language.startswith("pt"):
            text = text.replace('§', 'parágrafo')
        else:
            text = text.replace('§', 'section')

        return text

    def normalize_punctuation(self, text: str) -> str:
        """Normalize complex punctuation for better TTS prosody."""
        if not text:
            return ""

        # Ellipsis: ensure proper pause
        text = text.replace('…', '...')

        # Multiple exclamation/question marks → single
        text = re.sub(r'!{2,}', '!', text)
        text = re.sub(r'\?{2,}', '?', text)

        # Semicolon → comma (more natural pause in speech)
        text = text.replace(';', ',')

        # Colon followed by lowercase → comma (enumerative colon)
        text = re.sub(r':\s+(?=[a-záéíóúàâêôãõç])', ', ', text)

        # Remove parenthetical markers but keep content
        text = re.sub(r'\(([^)]*)\)', r', \1, ', text)
        text = re.sub(r'\[([^\]]*)\]', r', \1, ', text)

        # Clean up double commas from transformations
        text = re.sub(r',\s*,', ',', text)

        return text

    def insert_pauses(self, text: str, style: str = "serene") -> str:
        """Insert subtle pause markers based on narration style.

        For 'serene' style (long reading), add slightly longer pauses
        after paragraph breaks. For 'didactic' style, add pauses after
        key explanatory phrases.
        """
        if not text:
            return ""

        if style == "serene":
            # Add extra space after paragraph-ending periods for longer pauses
            text = re.sub(r'\.\n\n', '.\n\n\n', text)
        elif style == "didactic":
            # No extra modifications needed; TTS handles didactic pacing
            pass

        return text
