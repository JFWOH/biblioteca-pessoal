"""Extrator híbrido de conceitos (Fase 2).

Heurística (n-gramas 1–3 + stopwords PT/EN) sempre disponível e determinística;
refino opcional via LLM local (Ollama, ``format=json``) que apenas FILTRA e
REPONDERA os candidatos — nunca inventa termos ausentes do texto. Qualquer
falha do LLM degrada graciosamente para o resultado heurístico (ADR-005).

Core puro: sem PyQt6 (ADR-006).
"""

import json
import logging
import re
import unicodedata
import urllib.request
from collections import Counter

from src.core.graph.stopwords import STOPWORDS

logger = logging.getLogger(__name__)

_TOKEN_RE = re.compile(r"\w+", re.UNICODE)
# Pontuação que marca início de sentença para o bônus de capitalização.
_SENTENCE_BREAK = set(".!?\n;:•—–")

_LLM_PROMPT = """Você é um extrator de conceitos de leitura. Do trecho abaixo, selecione os conceitos MAIS relevantes a partir da lista de candidatos (pode refinar a grafia, mas NÃO invente termos que não estejam no trecho).

Candidatos: {candidates}

Trecho:
\"\"\"{excerpt}\"\"\"

Responda APENAS com JSON no formato:
{{"concepts": [{{"name": "conceito", "relevance": 0.0}}]}}
Use no máximo {max_concepts} conceitos, relevance entre 0 e 1."""


def resolve_llm_model(ollama_url: str = "http://localhost:11434",
                      preferred: str | None = None, timeout: int = 3) -> str | None:
    """Escolhe um modelo instalado no Ollama para o refino (ou None).

    Mesma filosofia do agente proativo: favorece modelos leves/rápidos.
    Falha (Ollama fora) devolve None — o extrator segue só com a heurística.
    """
    try:
        req = urllib.request.Request(f"{ollama_url.rstrip('/')}/api/tags")
        with urllib.request.urlopen(req, timeout=timeout) as resp:
            data = json.loads(resp.read())
        installed = [m.get("name", "") for m in data.get("models", []) if m.get("name")]
    except Exception:
        return None
    if not installed:
        return None
    installed_bases = {}
    for name in installed:
        installed_bases.setdefault(name.split(":")[0], name)
    for pref in (preferred, "gemma4:e4b", "gemma3:4b", "gemma2:2b"):
        if not pref:
            continue
        if pref in installed:
            return pref
        base = pref.split(":")[0]
        if base in installed_bases:
            return installed_bases[base]
    return installed[0]


class ConceptExtractor:
    """Extrai conceitos de um texto (heurística + refino LLM opcional)."""

    def __init__(self, ollama_url: str = "http://localhost:11434",
                 llm_model: str | None = None, llm_timeout_s: int = 20):
        self.ollama_url = ollama_url.rstrip("/")
        self.llm_model = llm_model
        self.llm_timeout_s = llm_timeout_s

    # ── API ───────────────────────────────────────────────────────────

    def extract(self, text: str, max_concepts: int = 8,
                use_llm: bool = False) -> tuple[list[tuple[str, str, float]], str]:
        """Extrai conceitos do texto.

        Devolve ``(conceitos, metodo)`` onde conceitos é uma lista de
        ``(name normalizado, display_name, weight 0-1)`` e metodo é
        ``'heuristic'`` ou ``'llm'`` (este só quando o refino sucedeu).
        """
        if not text or not text.strip():
            return [], "heuristic"
        # Pool maior que o pedido para dar escolha ao LLM.
        pool = max(max_concepts * 2, 12)
        candidates = self._heuristic(text, pool)
        if use_llm and self.llm_model and candidates:
            try:
                refined = self._llm_refine(text, candidates, max_concepts)
                if refined:
                    return refined, "llm"
            except Exception as exc:
                logger.debug("Refino LLM falhou (fallback heurístico): %s", exc)
        return candidates[:max_concepts], "heuristic"

    @staticmethod
    def normalize(term: str) -> str:
        """casefold + remove acentos (NFKD) + colapsa espaços."""
        decomposed = unicodedata.normalize("NFKD", term.casefold())
        stripped = "".join(c for c in decomposed if not unicodedata.combining(c))
        return " ".join(stripped.split())

    # ── Heurística ────────────────────────────────────────────────────

    def _heuristic(self, text: str, max_concepts: int) -> list[tuple[str, str, float]]:
        tokens: list[tuple[str, str, bool]] = []  # (surface, norm, inicia_sentenca)
        prev_end = 0
        for m in _TOKEN_RE.finditer(text):
            gap = text[prev_end:m.start()]
            starts = prev_end == 0 or any(ch in _SENTENCE_BREAK for ch in gap)
            tokens.append((m.group(), self.normalize(m.group()), starts))
            prev_end = m.end()

        short_text = len(text) < 400
        # norm -> [freq, Counter(surfaces), capitalizado_fora_de_inicio]
        counts: dict[str, list] = {}
        n = len(tokens)
        for i in range(n):
            for size in (1, 2, 3):
                if i + size > n:
                    break
                gram = tokens[i:i + size]
                # N-grama não atravessa fronteira de sentença.
                if any(t[2] for t in gram[1:]):
                    break
                first, last = gram[0], gram[-1]
                # Bordas não podem ser stopwords nem números (interior pode:
                # "teoria DA relatividade").
                if first[1] in STOPWORDS or last[1] in STOPWORDS:
                    continue
                # Qualquer token com dígito sai (anos, números de página,
                # colagens tipo "999Em" em PDFs mal extraídos).
                if any(ch.isdigit() for t in gram for ch in t[1]):
                    continue
                norm = " ".join(t[1] for t in gram)
                if len(norm) < 3 or (size == 1 and len(norm) < 4):
                    continue
                surface = " ".join(t[0] for t in gram)
                cap_mid = first[0][:1].isupper() and not first[2]
                entry = counts.setdefault(norm, [0, Counter(), False])
                entry[0] += 1
                entry[1][surface] += 1
                entry[2] = entry[2] or cap_mid

        scored: list[tuple[str, str, float]] = []
        for norm, (freq, surfaces, cap_mid) in counts.items():
            size = norm.count(" ") + 1
            if size == 1 and freq < (1 if short_text else 2):
                continue
            ngram_bonus = 1.0 if size == 1 else (1.5 if size == 2 else 2.0)
            cap_bonus = 1.5 if cap_mid else 1.0
            score = freq * ngram_bonus * cap_bonus
            display = surfaces.most_common(1)[0][0]
            scored.append((norm, display, score))

        scored.sort(key=lambda r: (-r[2], r[0]))
        top = scored[:max_concepts]
        if not top:
            return []
        max_score = top[0][2]
        return [(name, display, round(score / max_score, 3))
                for name, display, score in top]

    # ── Refino LLM (opcional) ─────────────────────────────────────────

    def _llm_refine(self, text: str, candidates: list[tuple[str, str, float]],
                    max_concepts: int) -> list[tuple[str, str, float]]:
        prompt = _LLM_PROMPT.format(
            candidates=", ".join(c[1] for c in candidates),
            excerpt=text[:1200],
            max_concepts=max_concepts,
        )
        from src.core import ollama_client
        content = ollama_client.chat_once(
            self.ollama_url, self.llm_model,
            [{"role": "user", "content": prompt}],
            response_format="json", temperature=0.1, num_predict=512,
            timeout_s=self.llm_timeout_s,
        )
        # Saneamento (padrão do proactive_worker): pega do primeiro { ao último }.
        start, end = content.find("{"), content.rfind("}")
        if start < 0 or end <= start:
            return []
        parsed = json.loads(content[start:end + 1])

        norm_text = self.normalize(text)
        cand_by_name = {c[0]: c for c in candidates}
        best: dict[str, tuple[str, str, float]] = {}
        for item in parsed.get("concepts", []):
            if not isinstance(item, dict):
                continue
            raw = str(item.get("name", "")).strip()
            norm = self.normalize(raw)
            if not norm or len(norm) < 3:
                continue
            if norm in cand_by_name:
                display = cand_by_name[norm][1]
            elif norm in norm_text:
                display = raw  # refinou a grafia, mas o termo existe no texto
            else:
                continue  # inventado → descarta
            try:
                rel = float(item.get("relevance", 0.5))
            except (TypeError, ValueError):
                rel = 0.5
            rel = round(min(max(rel, 0.05), 1.0), 3)
            if norm not in best or rel > best[norm][2]:
                best[norm] = (norm, display, rel)
        out = sorted(best.values(), key=lambda r: (-r[2], r[0]))
        return out[:max_concepts]
