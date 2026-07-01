import json
import logging
from pathlib import Path
from datetime import datetime, timezone
from typing import Any, Dict, Optional

logger = logging.getLogger(__name__)

class TraceLogger:
    """Implementa o ADR-004: Structured Agent Trace Logger."""

    def __init__(self, session_id: str, traces_dir: str = "data/traces"):
        self.session_id = session_id
        self.traces_dir = Path(traces_dir)
        self.file_path = self.traces_dir / f"trace_{self.session_id}.jsonl"
        self._ensure_dir()

    def _ensure_dir(self):
        try:
            self.traces_dir.mkdir(parents=True, exist_ok=True)
        except Exception as e:
            logger.warning("Não foi possível criar o diretório de traces: %s", e)

    def _truncate_payload(self, payload: Any, max_length: int = 1000) -> Any:
        """Trunca dados longos recursivamente para evitar logs gigantes (higiene/sanitização)."""
        if isinstance(payload, str):
            if len(payload) > max_length:
                return payload[:max_length] + "... [TRUNCATED]"
            return payload
        elif isinstance(payload, dict):
            return {k: self._truncate_payload(v, max_length) for k, v in payload.items()}
        elif isinstance(payload, list):
            # Limita também listas grandes para evitar explosão de log
            truncated_list = [self._truncate_payload(item, max_length) for item in payload[:50]]
            if len(payload) > 50:
                truncated_list.append(f"... [+ {len(payload) - 50} items TRUNCATED]")
            return truncated_list
        return payload

    def emit(
        self,
        event_type: str,
        step: int,
        query: Optional[str] = None,
        book_id: Optional[int] = None,
        provenance: str = "local",
        confidence: Optional[float] = None,
        tool_name: Optional[str] = None,
        allowed: Optional[bool] = None,
        reason: Optional[str] = None,
        round_num: Optional[int] = None,
        payload: Optional[Any] = None,
        error_type: Optional[str] = None,
        error_message: Optional[str] = None,
    ):
        """Emite um evento estruturado para o log append-friendly (JSONL)."""
        event = {
            "timestamp": datetime.now(timezone.utc).isoformat(),
            "session_id": self.session_id,
            "event_type": event_type,
            "step": step,
            "provenance": provenance,
        }

        if query is not None: event["query"] = query
        if book_id is not None: event["book_id"] = book_id
        if confidence is not None: event["confidence"] = confidence
        if tool_name is not None: event["tool_name"] = tool_name
        if allowed is not None: event["allowed"] = allowed
        if reason is not None: event["reason"] = reason
        if round_num is not None: event["round"] = round_num
        if error_type is not None: event["error_type"] = error_type
        if error_message is not None: event["error_message"] = error_message
        
        if payload is not None:
            event["payload"] = self._truncate_payload(payload)

        try:
            with open(self.file_path, "a", encoding="utf-8") as f:
                f.write(json.dumps(event, ensure_ascii=False) + "\n")
        except Exception as e:
            # Fallback seguro: Loga apenas no sistema padrão, nunca quebra o RAG
            logger.warning("Falha ao escrever trace event %s no arquivo %s: %s", event_type, self.file_path, e)
