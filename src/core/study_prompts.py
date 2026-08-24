"""Construção de prompts para as ações de estudo do assistente de leitura.

Lógica pura (sem GUI / sem PyQt6 — ADR-006) e testável: dado um tipo de ação
e o texto da página/trecho atual, devolve a instrução a ser enviada ao
assistente RAG. Usado pelas ações "Estudar" do leitor e pela ação
"Simplificar" do menu de seleção.

Todos os templates seguem os mesmos critérios objetivos (revisão A/B Q.3):
ancorados no trecho, com limite de tamanho explícito, citando a fonte quando
recorrem à biblioteca, e sempre respondendo em pt-BR.
"""

from __future__ import annotations

from typing import Optional

# Regra de idioma comum a TODAS as ações de estudo (revisão A/B, critério
# "idioma"): o trecho pode estar em qualquer língua (a biblioteca tem muito
# livro em inglês), mas a resposta é para o leitor — sempre em pt-BR. Sem
# esta linha o modelo tende a responder no idioma do trecho.
_LANG_RULE = (
    "Responda em português do Brasil, mesmo que o trecho esteja em outro idioma."
)

# Ações de estudo suportadas → instrução base (em PT-BR).
_STUDY_TEMPLATES: dict[str, str] = {
    "explain_page": (
        "Explique de forma didática e clara o conteúdo do trecho abaixo, "
        "em no máximo 200 palavras. "
        "Destaque os conceitos-chave e defina os termos técnicos que aparecerem. "
        "Explique o que está no trecho; se precisar de conhecimento externo, "
        "marque a frase com '(fora do trecho)'. "
        "Se a biblioteca tiver material relacionado, conecte-o citando a fonte. "
        f"{_LANG_RULE}"
    ),
    "summarize": (
        "Resuma os pontos principais do trecho abaixo em no máximo 5 tópicos "
        "curtos (uma linha cada), "
        "preservando a ordem das ideias e sem adicionar informação que não esteja "
        f"no texto. {_LANG_RULE}"
    ),
    "glossary": (
        "Extraia um glossário de no máximo 8 termos técnicos ou conceitos "
        "importantes do trecho abaixo. "
        "Para cada item use o formato '- **termo** — definição curta (1 linha)'. "
        f"Inclua apenas termos que de fato apareçam no texto. {_LANG_RULE}"
    ),
    "flashcards": (
        "Gere de 3 a 6 flashcards de estudo cobrindo os conceitos centrais do trecho abaixo. "
        "Use exatamente o formato, um por bloco:\nP: <pergunta>\nR: <resposta>\n"
        "As perguntas devem ser respondíveis apenas com o conteúdo do trecho. "
        f"{_LANG_RULE}"
    ),
    "simplify": (
        "Reescreva o trecho abaixo em linguagem simples, para quem não conhece o "
        "assunto, em no máximo 4 frases. "
        "Troque o jargão por palavras do dia a dia; se um termo técnico for "
        "indispensável, explique-o entre parênteses na primeira vez. "
        "Diga apenas o que está no trecho — não acrescente exemplos, opiniões nem "
        f"informação de fora. {_LANG_RULE}"
    ),
}

STUDY_ACTIONS = tuple(_STUDY_TEMPLATES.keys())


_FLASHCARD_QA_PROMPT = (
    "Você cria flashcards de estudo. A partir do INSIGHT abaixo, gere UM "
    "flashcard: uma pergunta clara e específica cuja resposta seja o conteúdo "
    "essencial do insight (destile a resposta; não copie o insight inteiro). "
    "Não invente fatos que não estejam no insight.\n\n"
    "INSIGHT:\n'''\n{text}\n'''\n\n"
    'Responda APENAS com JSON no formato: {{"pergunta": "...", "resposta": "..."}}'
)


def build_flashcard_qa_prompt(text: Optional[str]) -> Optional[str]:
    """Prompt para transformar um insight em par pergunta/resposta (1 card)."""
    clean = (text or "").strip()
    if not clean:
        return None
    return _FLASHCARD_QA_PROMPT.format(text=clean[:1500])


def parse_flashcard_qa(content: Optional[str]) -> Optional[tuple[str, str]]:
    """Extrai (pergunta, resposta) da resposta JSON do modelo.

    Saneia a resposta (pega do primeiro '{' ao último '}') e aceita as chaves
    pergunta/resposta ou front/back. Devolve None se inválida/incompleta.
    """
    import json

    raw = (content or "").strip()
    start, end = raw.find("{"), raw.rfind("}")
    if start < 0 or end <= start:
        return None
    try:
        data = json.loads(raw[start:end + 1])
    except json.JSONDecodeError:
        return None
    if not isinstance(data, dict):
        return None
    front = str(data.get("pergunta") or data.get("front") or "").strip()
    back = str(data.get("resposta") or data.get("back") or "").strip()
    if not front or not back:
        return None
    return front, back


def _format_concepts(concepts: Optional[list[str]]) -> str:
    """Bloco de contexto com os conceitos-chave do livro (ou vazio).

    Degradação graciosa (ADR-005): grafo vazio / sem conceitos → string vazia,
    e o prompt fica idêntico ao anterior.
    """
    if not concepts:
        return ""
    names = [str(c).strip() for c in concepts if str(c).strip()]
    if not names:
        return ""
    # Limita para não inflar o prompt; os conceitos vêm ordenados por peso.
    joined = ", ".join(names[:12])
    return (
        "\n\nConceitos-chave deste livro (segundo o grafo de conceitos da "
        f"biblioteca), para orientar o foco: {joined}."
    )


_WORD_WISE_PROMPT = (
    "Explique em português, de forma curta e direta (1 a 2 frases), o que "
    "significa o termo abaixo NO CONTEXTO em que ele aparece. Vá direto à "
    "definição — sem repetir o termo como se fosse a resposta, sem "
    "introduções do tipo 'o termo significa'.\n\n"
    "TERMO: {term}{context_block}"
)


def _format_word_wise_context(context: Optional[str]) -> str:
    """Bloco de contexto (trecho da página) para desambiguar o termo.

    Degradação graciosa (ADR-005): sem contexto, o prompt define o termo
    isoladamente (string vazia, o prompt fica só com o termo).
    """
    clean = (context or "").strip()
    if not clean:
        return ""
    return f"\n\nCONTEXTO (trecho da página onde o termo aparece):\n'''\n{clean[:800]}\n'''"


def build_word_wise_prompt(term: Optional[str], context: Optional[str] = None) -> Optional[str]:
    """Monta a instrução da definição rápida (Word Wise, tarefa 3.4).

    Args:
        term: a seleção curta (palavra/termo, tipicamente até ~4 palavras)
            que o leitor quer entender rapidamente.
        context: trecho da página onde o termo aparece, usado para
            desambiguar o sentido (ex.: "banco" financeiro vs. móvel).
            Opcional — sem ele, o termo é definido isoladamente.

    Returns:
        A instrução completa, ou ``None`` se o termo estiver vazio. Tarefa
        rápida: o chamador deve usar o LLM com ``think=False`` e pedir
        resposta curta (mesmo padrão de build_flashcard_qa_prompt).
    """
    clean_term = (term or "").strip()
    if not clean_term:
        return None
    return _WORD_WISE_PROMPT.format(
        term=clean_term, context_block=_format_word_wise_context(context))


def build_study_prompt(action_type: str, text: Optional[str],
                       concepts: Optional[list[str]] = None) -> Optional[str]:
    """Monta a instrução para uma ação de estudo.

    Args:
        action_type: uma das chaves em ``STUDY_ACTIONS``.
        text: texto da página/trecho atual.
        concepts: conceitos-chave do livro (grafo) para enriquecer o foco —
            especialmente na geração de flashcards (tarefa 3.3). Quando vazio
            ou ausente, o prompt é idêntico ao anterior (degradação graciosa).

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
    return f"{template}{_format_concepts(concepts)}\n\nTrecho:\n'''\n{clean}\n'''"
