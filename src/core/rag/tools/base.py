from typing import TypedDict, List, Dict, Any, Optional

class ToolOutput(TypedDict, total=False):
    status: str          # "success" ou "error"
    data: List[Dict[str, Any]]  # Lista normalizada: [{'text': ..., 'page': ..., 'title': ...}]
    provenance: str      # "local" ou "web"
    error_message: str   # Preenchido apenas se status == "error"
    confidence_score: float
    metadata: Optional[Dict[str, Any]]

def create_tool_output(
    status: str,
    data: List[Dict[str, Any]],
    provenance: str = "local",
    error_message: str = "",
    confidence: float = 1.0,
    metadata: Optional[Dict[str, Any]] = None
) -> ToolOutput:
    output: ToolOutput = {
        "status": status,
        "data": data,
        "provenance": provenance,
        "error_message": error_message,
        "confidence_score": confidence
    }
    if metadata is not None:
        output["metadata"] = metadata
    else:
        output["metadata"] = {
            "tool_name": "",
            "latency_ms": None,
            "result_count": len(data) if isinstance(data, list) else 0,
            "error_type": None,
            "error_message": error_message if status == "error" else None
        }
    return output
