import time
from typing import List, Set, Tuple

# ── Orçamentos do agente por tier de hardware ──────────────────────────────────
# Revisão de engenharia 2026-07-05 §1.4: os orçamentos eram constantes
# hardcoded calibradas para o pior caso observado NUMA máquina só — "num Tier C
# (CPU), 150s ainda corta; num Tier A, é folga demais". O tier vem do
# HardwareCapabilityService (mesma classificação usada para escolher o modelo).
#
#   Tier A (GPU > 10GB VRAM): cada rodada é rápida — vale gastar o orçamento em
#     MAIS rodadas de ferramentas e menos tempo ocioso de folga.
#   Tier B (padrão / GPU menor): valores medidos e calibrados nesta máquina —
#     o comportamento de hoje, preservado como referência.
#   Tier C (CPU, RAM < 8GB): uma única rodada pode levar minutos; corta rodadas
#     e alarga MUITO o tempo, para não abortar no meio da 1ª resposta.
TIER_BUDGETS: dict[str, Tuple[int, int]] = {
    "Tier A": (6, 90_000),
    "Tier B": (5, 150_000),
    "Tier C": (3, 300_000),
}

# Tier B é o default universal (mesma escolha do HardwareCapabilityService
# quando a detecção falha). Os defaults do AgentState apontam para ele — antes
# divergiam do call site real do orchestrator (20000 vs 150000).
DEFAULT_MAX_ROUNDS, DEFAULT_MAX_TIME_MS = TIER_BUDGETS["Tier B"]


def budget_for_tier(tier: str | None) -> Tuple[int, int]:
    """``(max_rounds, max_time_ms)`` do tier; Tier B para tier desconhecido/None."""
    return TIER_BUDGETS.get(tier or "", (DEFAULT_MAX_ROUNDS, DEFAULT_MAX_TIME_MS))


class AgentState:
    def __init__(self, session_id: str, max_rounds: int = DEFAULT_MAX_ROUNDS,
                 max_time_ms: int = DEFAULT_MAX_TIME_MS):
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
