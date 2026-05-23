import time
from typing import List, Any

class AgentState:
    def __init__(self, max_rounds: int = 5, max_time_ms: int = 20000):
        self.max_rounds = max_rounds
        self.max_time_ms = max_time_ms
        self.start_time = time.time()
        
        self.current_round = 0
        self.history: List[dict] = []
        self.called_tools: List[str] = []
        self.provenance = "local"  # Fica "web" se qualquer dado vier de fora
        self.confidence_score = 1.0
        self.last_results_digest = ""  # Para heurística de Early-Exit

    def update_provenance(self, source: str):
        if source == "web":
            self.provenance = "web"

    def is_budget_ok(self) -> bool:
        elapsed_ms = (time.time() - self.start_time) * 1000
        if self.current_round >= self.max_rounds:
            return False
        if elapsed_ms > self.max_time_ms:
            return False
        return True
