"""Revisão da tradução automática pelo agente principal (gemma4 via Ollama).

O NLLB é rápido mas comete falhas conhecidas em texto real: trechos que ficam
sem traduzir, repetições e lacunas. Este módulo faz um passe de PÓS-EDIÇÃO:
o LLM local recebe o original + o rascunho do NLLB e devolve a tradução
revisada. Falha em qualquer ponto (Ollama fora, resposta inválida) devolve
None e o chamador usa o rascunho — a revisão nunca piora nada (ADR-005).

Core puro (ADR-006): urllib, sem Qt.
"""

import json
import logging
import urllib.request

logger = logging.getLogger(__name__)

_REVISION_PROMPT = """Você é um revisor profissional de traduções inglês→português brasileiro.

Abaixo estão o TEXTO ORIGINAL e uma TRADUÇÃO AUTOMÁTICA que pode conter falhas: trechos deixados em inglês, palavras coladas ou quebradas, repetições e lacunas.

Reescreva a tradução corrigindo essas falhas — fiel ao original, completa e fluida em português. NÃO adicione comentários, notas ou explicações: responda SOMENTE com o texto da tradução revisada.

TEXTO ORIGINAL:
'''
{original}
'''

TRADUÇÃO AUTOMÁTICA:
'''
{draft}
'''"""


def revise_translation(original: str, draft: str,
                       ollama_url: str = "http://localhost:11434",
                       model: str | None = None,
                       timeout_s: int = 120) -> str | None:
    """Revisa o rascunho de tradução com o LLM local.

    Returns:
        Tradução revisada, ou None se a revisão não pôde ser feita/validada
        (chamador mantém o rascunho do NLLB).
    """
    original = (original or "").strip()
    draft = (draft or "").strip()
    if not original or not draft:
        return None

    if not model:
        # Mesma resolução de modelo do resto do app (leve por padrão).
        from src.core.graph.concept_extractor import resolve_llm_model
        model = resolve_llm_model(ollama_url)
    if not model:
        return None

    prompt = _REVISION_PROMPT.format(original=original[:6000], draft=draft[:6000])
    from src.core.ollama_defaults import OLLAMA_KEEP_ALIVE
    payload = {
        "model": model,
        "messages": [{"role": "user", "content": prompt}],
        "stream": False,
        "keep_alive": OLLAMA_KEEP_ALIVE,
        "options": {"temperature": 0.2, "num_predict": 2048},
    }
    try:
        req = urllib.request.Request(
            f"{ollama_url.rstrip('/')}/api/chat",
            data=json.dumps(payload).encode("utf-8"),
            headers={"Content-Type": "application/json"},
        )
        with urllib.request.urlopen(req, timeout=timeout_s) as resp:
            data = json.loads(resp.read())
        revised = ((data.get("message", {}) or {}).get("content") or "").strip()
        # Sanidade: revisão suspeita de truncamento/vazia → mantém o rascunho.
        if not revised or len(revised) < 0.4 * len(draft):
            logger.debug("Revisão descartada (curta demais: %d vs %d chars).",
                         len(revised), len(draft))
            return None
        return revised
    except Exception as exc:
        logger.debug("Revisão de tradução indisponível (%s) — usando o rascunho.", exc)
        return None
