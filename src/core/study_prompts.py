"""Construção de prompts para as ações de estudo do assistente de leitura.

Lógica pura (sem GUI / sem PyQt6 — ADR-006) e testável: dado um tipo de ação
e o texto da página/trecho atual, devolve a instrução a ser enviada ao
assistente RAG. Usado pelas ações "Estudar" do leitor.
"""

from __future__ import annotations

from typing import Optional

# Ações de estudo suportadas → instrução base (em PT-BR).
_STUDY_TEMPLATES: dict[str, str] = {
    "explain_page": (
        "Explique de forma didática e clara o conteúdo do trecho abaixo. "
        "Destaque os conceitos-chave e defina os termos técnicos que aparecerem. "
        "Se a biblioteca tiver material relacionado, conecte-o citando a fonte."
    ),
    "summarize": (
        "Resuma os pontos principais do trecho abaixo em tópicos curtos e objetivos, "
        "preservando a ordem das ideias e sem adicionar informação que não esteja no texto."
    ),
    "glossary": (
        "Extraia um glossário dos termos técnicos ou conceitos importantes do trecho abaixo. "
        "Para cada item use o formato '- **termo** — definição curta'. "
        "Inclua apenas termos que de fato apareçam no texto."
    ),
    "flashcards": (
        "Gere de 3 a 6 flashcards de estudo cobrindo os conceitos centrais do trecho abaixo. "
        "Use exatamente o formato, um por bloco:\nP: <pergunta>\nR: <resposta>\n"
        "As perguntas devem ser respondíveis apenas com o conteúdo do trecho."
    ),
}

STUDY_ACTIONS = tuple(_STUDY_TEMPLATES.keys())


def build_study_prompt(action_type: str, text: Optional[str]) -> Optional[str]:
    """Monta a instrução para uma ação de estudo.

    Args:
        action_type: uma das chaves em ``STUDY_ACTIONS``.
        text: texto da página/trecho atual.

    Returns:
        A instrução completa, ou ``None`` se a ação for desconhecida ou o
        texto estiver vazio.
    """
    template = _STUDY_TEMPLATES.get(action_type)
    if template is None:
        return None
    clean = (text or "").strip()
    if not clean:
        return None
    return f"{template}\n\nTrecho:\n'''\n{clean}\n'''"
