import logging
from typing import Dict, Any

logger = logging.getLogger(__name__)

class PolicyEngine:
    """Motor de Políticas para Ações do Agente.
    
    Resguarda a aplicação de Prompt Injection indireto bloqueando mutações
    de UI ou alterações de estado solicitadas por dados vindos de fontes inseguras (web).
    """

    @staticmethod
    def is_action_allowed(action_type: str, provenance: str, data: Dict[str, Any]) -> bool:
        """Verifica se uma ação solicitada pelo LLM/ferramenta é permitida.
        
        Regras (ADR-003):
        - highlight_book_text / highlight: Bloqueado se a proveniência for 'web'.
        - create_ai_bookmark / bookmark: Bloqueado se a proveniência for 'web'.
        - Qualquer outra alteração: Bloqueada se vier da web.
        """
        # Ações de leitura/busca local ou web são sempre permitidas
        # (inclui as tools de grafo — read-only sobre o GraphStore, Fase 3).
        if action_type in ("vector_search", "keyword_search", "cross_reference", "search_web",
                           "graph_concept_lookup", "graph_related_books", "graph_book_concepts"):
            return True

        # Trata mutações visuais da UI
        if provenance == "web":
            logger.warning(
                "Ação de UI '%s' BLOQUEADA pelo Policy Engine: Proveniência externa (web) não confiável.",
                action_type
            )
            return False

        # Validação extra de segurança para dados locais
        if action_type == "highlight":
            # Permite se o texto a destacar for pequeno/limitado
            text = data.get("text_to_find", "")
            if len(text) > 1000:
                logger.warning("Ação 'highlight' bloqueada: texto excede limite seguro (1000 chars).")
                return False
            return True

        if action_type == "bookmark":
            note = data.get("note", "")
            if len(note) > 1000:
                logger.warning("Ação 'bookmark' bloqueada: nota excede limite seguro (1000 chars).")
                return False
            return True

        return True
