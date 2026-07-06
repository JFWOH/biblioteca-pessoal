import time
from typing import List, Set

class AgentState:
    def __init__(self, session_id: str, max_rounds: int = 5, max_time_ms: int = 20000):
        self.session_id = session_id
        self.max_rounds = max_rounds
        self.max_time_ms = max_time_ms
        self.start_time = time.time()
        
        self.current_round = 0
        self.history: List[dict] = []
        self.called_tools: List[str] = []
        self.provenance = "local"  # Fica "web" se qualquer dado vier de fora
        self.confidence_score = 1.0
        self.last_results_digest = ""  # Para heurística de Early-Exit antiga
        
        # Novos campos ADR-002 aprovados na Fase 4A
        self.sources_used: Set[str] = set()
        self.books_consulted: Set[str] = set()
        self.last_result_hash: str = ""
        self.repeated_result_count: int = 0
        self.errors: List[dict] = []
        self.web_seen: bool = False
        self.ui_mutation_requested: bool = False

    def add_error(self, error_type: str, message: str):
        self.errors.append({"type": error_type, "message": message})

    def update_provenance(self, source: str):
        self.sources_used.add(source)
        if source == "web" or source == "search_web":
            self.provenance = "web"
            self.web_seen = True

    def is_budget_ok(self) -> bool:
        elapsed_ms = (time.time() - self.start_time) * 1000
        if self.current_round >= self.max_rounds:
            return False
        if elapsed_ms > self.max_time_ms:
            return False
        return True
