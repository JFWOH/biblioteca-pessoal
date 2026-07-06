"""Cliente unificado para o /api/chat do Ollama (core puro, ADR-006).

Consolida as ~6 implementações independentes de "montar payload + chamar
/api/chat via urllib" espalhadas pelo core e pelos workers da GUI — cada
uma com seu próprio histórico de bugs (a resposta cortada do RAG nasceu
exatamente dessa duplicação; revisão de engenharia 2026-07-05 §3.1).

``chat_once`` cobre os chamadores não-streaming (extração de conceitos,
revisão de tradução, flashcard QA, síntese do dossiê, agente proativo).
``stream_chat`` cobre o streaming token a token do Orchestrator, incluindo
os campos ``thinking``/``tool_calls`` que modelos de raciocínio emitem.
Cada chamador mantém sua própria lógica de negócio (cancelamento,
continuação por comprimento, validação/parsing da resposta) — o cliente
só resolve o transporte HTTP e o formato do payload.
"""

from __future__ import annotations

import json
import urllib.request
from typing import Any, Generator, Optional

from src.core.ollama_defaults import OLLAMA_KEEP_ALIVE

DEFAULT_TIMEOUT_S = 120


def build_chat_payload(
    model: str,
    messages: list[dict],
    *,
    stream: bool = False,
    tools: Optional[list[dict]] = None,
    response_format: Optional[str] = None,
    temperature: Optional[float] = None,
    num_predict: int = 4096,
    num_ctx: Optional[int] = None,
    repeat_penalty: Optional[float] = None,
    repeat_last_n: Optional[int] = None,
    keep_alive: str = OLLAMA_KEEP_ALIVE,
    think: Optional[bool] = None,
) -> dict[str, Any]:
    """Monta o payload de ``/api/chat`` com as opções comuns a todos os chamadores.

    ``think=False`` desliga a fase de raciocínio dos modelos thinking —
    medido em 2026-07-06: flashcard P/R no gemma4:e4b cai de 9,8s para
    3,3s (e no 12b de 65s para 3,9s) sem perder validade do JSON. Só usar
    em tarefas estruturadas; tarefas profundas (RAG, dossiê, proativo)
    mantêm o raciocínio por decisão de qualidade (lição do commit a1cc513).
    ``None`` não envia o campo (default do modelo); o Ollama aceita
    ``think=False`` sem erro mesmo em modelos não-thinking (verificado).
    """
    options: dict[str, Any] = {"num_predict": num_predict}
    if num_ctx is not None:
        options["num_ctx"] = num_ctx
    if temperature is not None:
        options["temperature"] = temperature
    if repeat_penalty is not None:
        options["repeat_penalty"] = repeat_penalty
    if repeat_last_n is not None:
        options["repeat_last_n"] = repeat_last_n

    payload: dict[str, Any] = {
        "model": model,
        "messages": messages,
        "stream": stream,
        "keep_alive": keep_alive,
        "options": options,
    }
    if tools:
        payload["tools"] = tools
    if response_format:
        payload["format"] = response_format
    if think is not None:
        payload["think"] = think
    return payload


def chat_once(
    ollama_url: str,
    model: str,
    messages: list[dict],
    *,
    response_format: Optional[str] = None,
    temperature: Optional[float] = None,
    num_predict: int = 4096,
    timeout_s: int = DEFAULT_TIMEOUT_S,
    think: Optional[bool] = None,
) -> str:
    """Chamada não-streaming: devolve ``message.content`` (stripped, pode ser "").

    Propaga exceções de rede/timeout/JSON — cada chamador decide como
    degradar (ADR-005); todos os chamadores atuais já envolvem isto num
    try/except próprio.
    """
    payload = build_chat_payload(
        model, messages, stream=False,
        response_format=response_format,
        temperature=temperature, num_predict=num_predict,
        think=think,
    )
    req = urllib.request.Request(
        f"{ollama_url.rstrip('/')}/api/chat",
        data=json.dumps(payload).encode("utf-8"),
        headers={"Content-Type": "application/json"},
    )
    with urllib.request.urlopen(req, timeout=timeout_s) as resp:
        data = json.loads(resp.read())
    return ((data.get("message", {}) or {}).get("content") or "").strip()


def stream_chat(
    ollama_url: str,
    model: str,
    messages: list[dict],
    *,
    tools: Optional[list[dict]] = None,
    temperature: Optional[float] = None,
    num_predict: int = 4096,
    num_ctx: Optional[int] = None,
    repeat_penalty: Optional[float] = None,
    repeat_last_n: Optional[int] = None,
    timeout_s: int = DEFAULT_TIMEOUT_S,
) -> Generator[dict, None, None]:
    """Chamada streaming: yield de cada mensagem do NDJSON do Ollama.

    Cada item gerado é o dict ``message`` do chunk (``content``,
    ``thinking``, ``tool_calls``, conforme o modelo emitir), acrescido de
    ``done``/``done_reason`` do envelope externo. Linhas vazias ou
    inválidas são silenciosamente ignoradas (mesmo comportamento das 3
    implementações que este cliente substitui). Cancelamento cooperativo,
    acumulação de tool_calls e retomada por comprimento continuam a
    critério do chamador — são específicos do loop do agente RAG.
    """
    payload = build_chat_payload(
        model, messages, stream=True, tools=tools,
        temperature=temperature, num_predict=num_predict, num_ctx=num_ctx,
        repeat_penalty=repeat_penalty, repeat_last_n=repeat_last_n,
    )
    req = urllib.request.Request(
        f"{ollama_url.rstrip('/')}/api/chat",
        data=json.dumps(payload).encode("utf-8"),
        headers={"Content-Type": "application/json"},
        method="POST",
    )
    with urllib.request.urlopen(req, timeout=timeout_s) as resp:
        for line in resp:
            if not line:
                continue
            try:
                chunk = json.loads(line.decode("utf-8"))
            except (json.JSONDecodeError, AttributeError, UnicodeDecodeError):
                continue
            msg = dict(chunk.get("message", {}) or {})
            msg["done"] = chunk.get("done", False)
            msg["done_reason"] = chunk.get("done_reason", "")
            yield msg
