import hashlib
import json
import logging
import uuid
from typing import List, Dict, Any, Optional, Generator

from src.core.rag.agent_state import AgentState
from src.core.rag.tools.base import ToolOutput, create_tool_output
from src.core.rag.trace_logger import TraceLogger

logger = logging.getLogger(__name__)

# Lista de Stopwords em Português e Inglês para Heurística Determinística Offline
PORTUGUESE_STOPWORDS = {
    "a", "o", "os", "as", "um", "uma", "uns", "umas", "de", "do", "da", "dos", "das", "em", "no", "na", "nos", "nas",
    "para", "por", "com", "sem", "sob", "sobre", "atras", "detras", "ante", "apos", "que", "se", "como", "ou", "mas",
    "e", "nem", "ou", "senao", "porque", "pois", "portanto", "contudo", "entretanto", "todavia", "eu", "tu", "ele",
    "ela", "nos", "vos", "eles", "elas", "me", "te", "se", "nos", "vos", "lhe", "lhes", "o", "a", "os", "as", "mim",
    "ti", "si", "este", "esta", "estes", "estas", "esse", "essa", "esses", "essas", "aquele", "aquela", "aqueles",
    "aquela", "isto", "isso", "aquilo", "meu", "minha", "meus", "minhas", "teu", "tua", "teus", "tuas", "seu", "sua",
    "seus", "suas", "nosso", "nossa", "nossos", "nossas", "vosso", "vossa", "vossos", "vossas", "ser", "estar", "ter",
    "haver", "fazer", "ir", "vir", "poder", "querer", "dizer", "dar", "saber", "foi", "foram", "era", "eram", "sao",
    "sou", "somos", "sois", "es", "estou", "esta", "estamos", "estao", "estive", "estivemos", "estiveram", "tenho",
    "tem", "temos", "tem", "tinha", "tinham", "tive", "tivemos", "tiveram", "fiz", "fez", "fazemos", "fazem", "faria",
    "fariam", "faco", "faz", "fazeis", "ia", "iam", "fui", "fomos", "foram", "irei", "ira", "iremos", "irao", "vou",
    "vai", "vamos", "vao", "posso", "pode", "podemos", "podem", "podia", "podiam", "pude", "pudemos", "puderam", "um",
    "uns", "dois", "tres", "quatro", "cinco", "seis", "sete", "oito", "nove", "dez", "primeiro", "segundo", "terceiro",
    "primeiros", "segundos", "terceiros", "apenas", "muito", "pouco", "mais", "menos", "tampouco", "tambem", "nunca",
    "jamais", "sempre", "talvez", "acaso", "quiça", "sim", "nao", "bem", "mal", "muito", "pouco", "quase", "tanto",
    "quanto", "como", "onde", "aonde", "donde", "quando", "como", "porque", "qual", "quais", "quem", "cujo", "cuja",
    "cujos", "cujas", "quanto", "quanta", "quantos", "quantas", "bastante", "bastantes", "outrem", "nada", "tudo",
    "alguem", "ninguem", "algo", "cada", "qualquer", "quaisquer", "algum", "alguma", "alguns", "algumas", "nenhum",
    "nenhuma", "nenhuns", "nenhumas", "todo", "toda", "todos", "todas", "outro", "outra", "outros", "outras", "mesmo",
    "mesma", "mesmos", "mesmas", "proprio", "propria", "proprios", "proprias", "vários", "várias", "diverso", "diversa",
    "diversos", "diversas"
}


class Orchestrator:
    """Orquestrador do loop de agente RAG resiliente e tolerante a falhas.
    
    Gerencia a execução de ferramentas com tratamento de exceções, fallbacks elegantes
    e heurísticas de encerramento precoce (Early-Exit).
    """

    def __init__(self, engine: Any):
        """Inicializa o orquestrador com a referência do motor RAG central."""
        self.engine = engine

    def _reformulate_query(self, query: str) -> List[str]:
        """Gera uma lista de consultas (queries) alternativas para a busca web.
        
        Tenta enriquecimento via LLM se o Ollama estiver online. Caso contrário,
        usa regras heurísticas de mapeamento de conceitos históricos (ex: Cardano)
        e filtragem determinística de stopwords.
        """
        alternatives: List[str] = []
        
        # 1. Enriquecimento opcional via LLM (Ollama)
        try:
            if hasattr(self.engine, "is_ollama_available") and self.engine.is_ollama_available():
                system_prompt = (
                    "Você é um reescritor de buscas especialista. "
                    "Sua tarefa é reescrever a pergunta conversacional ou frase longa fornecida pelo usuário "
                    "em exatamente 3 a 5 palavras-chave cirúrgicas e objetivas otimizadas para motores de busca. "
                    "Retorne APENAS as palavras-chave separadas por espaço, sem explicações ou aspas adicionais."
                )
                
                messages = [
                    {"role": "system", "content": system_prompt},
                    {"role": "user", "content": f"Reescreva para busca: '{query}'"}
                ]
                
                payload_dict = {
                    "model": self.engine._llm_model.strip(),
                    "messages": messages,
                    "stream": False,
                    "options": {"temperature": 0.1}
                }

                payload = json.dumps(payload_dict).encode("utf-8")
                endpoint = f"{self.engine._ollama_url.rstrip('/')}/api/chat"
                
                import urllib.request
                req = urllib.request.Request(
                    endpoint,
                    data=payload,
                    headers={"Content-Type": "application/json"},
                    method="POST",
                )
                with urllib.request.urlopen(req, timeout=5) as resp:
                    data = json.loads(resp.read())
                
                reformulated = data.get("message", {}).get("content", "").strip()
                reformulated = reformulated.replace('"', '').replace("'", "").strip()
                if reformulated:
                    alternatives.append(reformulated)
        except Exception as exc:
            logger.warning("Falha ao reformular via LLM: %s", exc)

        # 2. Camada Heurística Determinística (Sempre disponível offline)
        query_lower = query.lower()
        
        # 2a. Mapeamento de termos famosos (Caso Cardano)
        if "cardano" in query_lower:
            alternatives.append("Girolamo Cardano Liber de ludo aleae probability")
            alternatives.append("Cardano Book on Games of Chance probability")
            alternatives.append("Cardano jogos de azar probabilidade")
            alternatives.append("Cardano história probabilidade")

        # 2b. Filtragem de Stopwords geral (TF-IDF-like heurística)
        words = query.split()
        filtered_words = []
        for word in words:
            clean_word = word.strip('.,;:!?()"\'')
            if clean_word.lower() not in PORTUGUESE_STOPWORDS and len(clean_word) > 2:
                filtered_words.append(clean_word)

        if filtered_words:
            generic_keywords = " ".join(filtered_words[:5])
            if generic_keywords not in alternatives:
                alternatives.append(generic_keywords)

        # 3. Garante que a query original esteja presente como último recurso
        if query not in alternatives:
            alternatives.append(query)
            
        return alternatives

    def execute_vector_search(self, query: str, book_id: Optional[int] = None, state: Optional[AgentState] = None, trace_logger: Optional[TraceLogger] = None) -> ToolOutput:
        """Executa a busca vetorial semântica."""
        if state:
            state.called_tools.append("vector_search")
            if book_id is not None:
                state.books_consulted.add(str(book_id))
            
        try:
            # Tenta busca vetorial no motor RAG
            hits = self.engine.search_similar(query, n_results=5, book_id=book_id)
            data = [
                {
                    "text": h["document"],
                    "page": (h["metadata"].get("page_number") or 0) + 1,
                    "title": h["metadata"].get("title", ""),
                    "author": h["metadata"].get("author", ""),
                    "book_id": h["metadata"].get("book_id"),
                }
                for h in hits
            ]
            confidence = self._confidence_from_distances([h.get("distance") for h in hits])
            return create_tool_output(
                status="success",
                data=data,
                provenance="local",
                confidence=confidence
            )
        except Exception as exc:
            logger.warning("vector_search falhou, iniciando fallback para keyword_search: %s", exc)
            if state:
                state.add_error("VectorSearchError", str(exc))
                state.history.append({
                    "role": "system",
                    "content": f"vector_search falhou com erro: {exc}. Iniciando fallback para keyword_search no SQLite."
                })
            if trace_logger:
                trace_logger.emit("fallback_activated", step=state.current_round if state else 0, reason="vector_search_failed", payload={"error": str(exc)}, round_num=state.current_round if state else 0)
            
            # Lógica de Fallback: busca por palavras-chave
            try:
                hits = self.engine.keyword_search_db(query, book_id=book_id)
                data = [
                    {
                        "text": h.get("text", ""),
                        "page": h.get("page", 1),
                        "title": h.get("title", ""),
                        "author": h.get("author", ""),
                        "book_id": h.get("book_id"),
                    }
                    for h in hits
                ]
                return create_tool_output(
                    status="error",
                    data=data,
                    provenance="local",
                    error_message=str(exc),
                    confidence=0.5
                )
            except Exception as fallback_exc:
                logger.error("Fallback para keyword_search também falhou: %s", fallback_exc)
                if state:
                    state.add_error("KeywordSearchFallbackError", str(fallback_exc))
                return create_tool_output(
                    status="error",
                    data=[],
                    provenance="local",
                    error_message=f"Erro original: {exc}. Erro fallback: {fallback_exc}",
                    confidence=0.0
                )

    def execute_search_web(self, query: str, state: Optional[AgentState] = None, trace_logger: Optional[TraceLogger] = None) -> ToolOutput:
        """Executa a busca externa na web com suporte à Query Reformulation robusta.
        
        Executa sequencialmente as queries reformuladas até encontrar resultados válidos.
        Degrada de forma limpa para busca local em caso de falha de conexão em todas as buscas.
        """
        if state:
            state.called_tools.append("search_web")
            state.update_provenance("web")
            
        # 1. Camada de Otimização: Query Reformulation
        attempted_queries: List[str] = []
        if len(query.split()) > 4:
            try:
                attempted_queries = self._reformulate_query(query)
            except Exception as exc:
                logger.warning("Falha na geração de alternativas de query: %s", exc)
                attempted_queries = [query]
        else:
            attempted_queries = [query]
            
        if not attempted_queries:
            attempted_queries = [query]

        provider_errors: List[str] = []
        raw_result_count = 0
        normalized_results = []
        successful_query = None

        from src.core.rag.tools.web_search import search_duckduckgo, normalize_web_result

        # 2. Execução Otimizada: Tentativas sequenciais robustas
        for q in attempted_queries:
            try:
                logger.info("Tentando busca externa DuckDuckGo para: '%s'", q)
                raw_res = search_duckduckgo(q, provider_errors)
                if raw_res:
                    raw_result_count = len(raw_res)
                    # Normaliza de forma flexível as chaves (href/url/snippet/body)
                    for item in raw_res:
                        norm = normalize_web_result(item)
                        if norm:
                            normalized_results.append(norm)
                    
                    if normalized_results:
                        successful_query = q
                        break
            except Exception as exc:
                logger.warning("Busca falhou para a query '%s': %s", q, exc)
                provider_errors.append(f"Busca para '{q}' lançou exceção: {exc}")

        # 3. Formatação do contrato ToolOutput com os metadados enriquecidos exigidos
        metadata = {
            "tool_name": "search_web",
            "latency_ms": None,
            "provider": "duckduckgo_search",
            "attempted_queries": attempted_queries,
            "successful_query": successful_query,
            "raw_result_count": raw_result_count,
            "normalized_result_count": len(normalized_results),
            "provider_errors": provider_errors
        }

        if normalized_results:
            # Requisito de Segurança 4: Não logar conteúdo completo, apenas metadados e trechos
            data = [
                {
                    "text": item["text"],
                    "title": item["title"],
                    "href": item["href"],
                }
                for item in normalized_results
            ]
            return create_tool_output(
                status="success",
                data=data,
                provenance="web",
                confidence=1.0,
                metadata=metadata
            )
        else:
            # Conforme requisito 7: Se todas as buscas falharem, retornar status="error" e erro amigável
            err_msg = "A busca externa falhou ou não retornou resultados úteis."
            logger.warning("search_web falhou em todas as tentativas: %s", err_msg)
            if state:
                state.add_error("WebSearchError", err_msg)
                state.history.append({
                    "role": "system",
                    "content": f"search_web falhou em todas as tentativas. Detalhe: {err_msg}"
                })
            if trace_logger:
                trace_logger.emit("fallback_activated", step=state.current_round if state else 0, reason="web_search_failed", payload={"error": err_msg}, round_num=state.current_round if state else 0)
            
            # Lógica de Degradação Elegante: busca local similar
            try:
                fallback_query = attempted_queries[0]
                hits = self.engine.search_similar(fallback_query, n_results=3)
                data = [
                    {
                        "text": h["document"],
                        "page": (h["metadata"].get("page_number") or 0) + 1,
                        "title": h["metadata"].get("title", ""),
                        "author": h["metadata"].get("author", ""),
                        "book_id": h["metadata"].get("book_id"),
                        "degraded_info": "Dado local retornado após degradação por falha de conexão na busca web."
                    }
                    for h in hits
                ]
                return create_tool_output(
                    status="error",
                    data=data,
                    provenance="local",
                    error_message=err_msg,
                    confidence=0.7,
                    metadata=metadata
                )
            except Exception as local_exc:
                logger.error("Busca local de fallback também falhou: %s", local_exc)
                if state:
                    state.add_error("WebFallbackToLocalError", str(local_exc))
                return create_tool_output(
                    status="error",
                    data=[],
                    provenance="local",
                    error_message=f"Erro de busca web: {err_msg}. Erro local de fallback: {local_exc}",
                    confidence=0.0,
                    metadata=metadata
                )

    def execute_keyword_search(self, term: str, book_id: Optional[int] = None, state: Optional[AgentState] = None) -> ToolOutput:
        """Executa a busca textual por palavras-chave exatas."""
        if state:
            state.called_tools.append("keyword_search")
            if book_id is not None:
                state.books_consulted.add(str(book_id))
            
        try:
            hits = self.engine.keyword_search_db(term, book_id=book_id)
            data = [
                {
                    "text": h.get("text", ""),
                    "page": h.get("page", 1),
                    "title": h.get("title", ""),
                    "author": h.get("author", ""),
                    "book_id": h.get("book_id"),
                }
                for h in hits
            ]
            return create_tool_output(
                status="success",
                data=data,
                provenance="local",
                confidence=1.0
            )
        except Exception as exc:
            logger.error("keyword_search falhou: %s", exc)
            if state:
                state.add_error("KeywordSearchError", str(exc))
            return create_tool_output(
                status="error",
                data=[],
                provenance="local",
                error_message=str(exc),
                confidence=0.0
            )

    def execute_cross_reference(self, topic: str, current_book_id: Optional[int], state: Optional[AgentState] = None) -> ToolOutput:
        """Executa a busca por referência cruzada excluindo o livro atual."""
        if state:
            state.called_tools.append("cross_reference")
            if current_book_id is not None:
                state.books_consulted.add(str(current_book_id))
            
        try:
            if self.engine._collection is not None and current_book_id is not None:
                emb = self.engine._get_embedding(topic)
                res = self.engine._collection.query(
                    query_embeddings=[emb],
                    n_results=5,
                    where={"book_id": {"$ne": current_book_id}},
                    include=["documents", "metadatas", "distances"],
                )
                formatted = []
                docs = (res.get("documents") or [[]])[0]
                metas = (res.get("metadatas") or [[]])[0]
                dists = (res.get("distances") or [[]])[0]
                for doc, meta in zip(docs, metas):
                    formatted.append({
                        "text": doc,
                        "page": (meta.get("page_number") or 0) + 1,
                        "title": meta.get("title", ""),
                        "author": meta.get("author", ""),
                        "book_id": meta.get("book_id"),
                    })
                return create_tool_output(
                    status="success",
                    data=formatted,
                    provenance="local",
                    confidence=self._confidence_from_distances(list(dists))
                )
            else:
                hits = self.engine.search_similar(topic, n_results=5)
                filtered_hits = [
                    h for h in hits
                    if h["metadata"].get("book_id") != current_book_id
                ]
                formatted = [
                    {
                        "text": h["document"],
                        "page": (h["metadata"].get("page_number") or 0) + 1,
                        "title": h["metadata"].get("title", ""),
                        "author": h["metadata"].get("author", ""),
                        "book_id": h["metadata"].get("book_id"),
                    }
                    for h in filtered_hits
                ]
                return create_tool_output(
                    status="success",
                    data=formatted,
                    provenance="local",
                    confidence=self._confidence_from_distances([h.get("distance") for h in filtered_hits])
                )
        except Exception as exc:
            logger.error("cross_reference falhou: %s", exc)
            if state:
                state.add_error("CrossReferenceError", str(exc))
            return create_tool_output(
                status="error",
                data=[],
                provenance="local",
                error_message=str(exc),
                confidence=0.0
            )

    @staticmethod
    def _confidence_from_distances(distances: List[Any]) -> float:
        """Deriva um score de confiança [0,1] das distâncias de cosseno do Chroma.

        Distância de cosseno: 0 = idêntico, ~2 = oposto → similaridade = 1 - d
        (limitada a [0,1]). A confiança é a média das similaridades dos hits
        retornados. Sem distâncias válidas (ex.: provedor sem esse campo),
        retorna 1.0 para preservar o comportamento anterior.
        """
        sims = [
            max(0.0, min(1.0, 1.0 - d))
            for d in distances
            if isinstance(d, (int, float)) and not isinstance(d, bool)
        ]
        if not sims:
            return 1.0
        return round(sum(sims) / len(sims), 3)

    def compute_results_digest(self, outputs: List[ToolOutput]) -> str:
        """Computa um hash MD5 determinista sobre os dados das ferramentas.
        
        Usado pela heurística de Early-Exit para verificar duplicidade de retornos.
        """
        core_data = [o.get("data", []) for o in outputs]
        serialized = json.dumps(core_data, sort_keys=True)
        return hashlib.md5(serialized.encode("utf-8")).hexdigest()

    def run_agent_loop(
        self,
        question: str,
        book_id: Optional[int] = None,
        max_rounds: int = 5,
        max_time_ms: int = 20000
    ) -> Dict[str, Any]:
        """Executa o loop de agente síncrono simplificado."""
        session_id = str(uuid.uuid4())
        trace_logger = TraceLogger(session_id)
        state = AgentState(session_id=session_id, max_rounds=max_rounds, max_time_ms=max_time_ms)
        logger.info("Iniciando loop resiliente de orquestração RAG.")
        trace_logger.emit("query_started", step=0, query=question, book_id=book_id)

        while state.is_budget_ok():
            state.current_round += 1
            round_outputs: List[ToolOutput] = []

            # Roteamento de Ferramentas Simulado:
            if "web" in question.lower() or "internet" in question.lower() or "atual" in question.lower():
                out = self.execute_search_web(question, state, trace_logger)
                round_outputs.append(out)
                state.update_provenance(out["provenance"])
            else:
                out = self.execute_vector_search(question, book_id=book_id, state=state, trace_logger=trace_logger)
                round_outputs.append(out)
                state.update_provenance(out["provenance"])

            if out["status"] == "error" and "keyword_search" not in state.called_tools:
                kw_out = self.execute_keyword_search(question, book_id=book_id, state=state)
                round_outputs.append(kw_out)

            digest = self.compute_results_digest(round_outputs)
            if state.last_result_hash and state.last_result_hash == digest:
                state.repeated_result_count += 1
                logger.info("Early-Exit ativado: resultados idênticos detectados no round %d.", state.current_round)
                trace_logger.emit("early_exit", step=state.current_round, reason="resultados_identicos", round_num=state.current_round)
                break
            
            state.last_result_hash = digest

            state.history.append({
                "round": state.current_round,
                "called_tools": list(state.called_tools),
                "provenance": state.provenance,
                "outputs": round_outputs
            })

            min_conf = min([o.get("confidence_score", 1.0) for o in round_outputs]) if round_outputs else 1.0
            state.confidence_score = min_conf

            if state.confidence_score >= 0.85 and state.current_round >= 2:
                logger.info("Encerramento precoce por alto score de confiança (%.2f).", state.confidence_score)
                trace_logger.emit("early_exit", step=state.current_round, reason="alta_confianca", confidence=state.confidence_score, round_num=state.current_round)
                break

        final_result = {
            "status": "success",
            "provenance": state.provenance,
            "confidence_score": state.confidence_score,
            "rounds_executed": state.current_round,
            "called_tools": state.called_tools,
            "history": state.history,
            "final_data": state.history[-1]["outputs"] if state.history else [],
            "sources_used": list(state.sources_used),
            "books_consulted": list(state.books_consulted),
            "repeated_result_count": state.repeated_result_count,
            "errors": state.errors,
            "web_seen": state.web_seen,
            "ui_mutation_requested": state.ui_mutation_requested,
        }
        trace_logger.emit("query_completed", step=state.current_round + 1, payload=final_result)
        return final_result

    def _call_chat_api(self, msgs: list, stream: bool = False, temperature: float | None = None) -> Any:
        """Helper para chamar o Ollama Chat API."""
        import urllib.request
        from src.core.rag_engine import _TOOLS_DEF
        options = {
            "num_predict": 4096,
            "num_ctx": 8192,
        }
        if temperature is not None:
            options["temperature"] = temperature

        payload_dict = {
            "model": self.engine._llm_model.strip(),
            "messages": msgs,
            "stream": stream,
            "tools": _TOOLS_DEF,
            "options": options,
        }

        payload = json.dumps(payload_dict).encode("utf-8")
        endpoint = f"{self.engine._ollama_url.rstrip('/')}/api/chat"
        req = urllib.request.Request(
            endpoint,
            data=payload,
            headers={"Content-Type": "application/json"},
            method="POST",
        )
        return urllib.request.urlopen(req, timeout=120)

    def _execute_tool_orchestrated(
        self,
        fn_name: str,
        args: dict,
        state: AgentState,
        trace_logger: TraceLogger,
        book_id: Optional[int] = None,
        ui_mutation_callback: Optional[callable] = None,
    ) -> str:
        """Executa a ferramenta usando métodos robustos e protegidos por política do Orquestrador."""
        from src.core.rag.policy_engine import PolicyEngine

        trace_logger.emit("tool_call_requested", step=state.current_round, tool_name=fn_name, payload=args, round_num=state.current_round)

        try:
            if fn_name == "search_web":
                out = self.execute_search_web(args.get("query", ""), state, trace_logger)
                return json.dumps(out.get("data", []), ensure_ascii=False)

            elif fn_name == "vector_search":
                bid = args.get("book_id")
                if isinstance(bid, str):
                    bid = int(bid) if bid.isdigit() else None
                elif bid is None:
                    bid = book_id
                out = self.execute_vector_search(args.get("query", ""), book_id=bid, state=state, trace_logger=trace_logger)
                formatted = [
                    {
                        "title": item["title"],
                        "author": item["author"],
                        "page": item["page"],
                        "book_id": item["book_id"],
                        "text": item["text"],
                    }
                    for item in out.get("data", [])
                ]
                return json.dumps(formatted, ensure_ascii=False)

            elif fn_name == "keyword_search":
                bid = args.get("book_id")
                if isinstance(bid, str):
                    bid = int(bid) if bid.isdigit() else None
                elif bid is None:
                    bid = book_id
                out = self.execute_keyword_search(args.get("term", ""), book_id=bid, state=state)
                return json.dumps(out.get("data", []), ensure_ascii=False)

            elif fn_name == "cross_reference":
                cbid = args.get("current_book_id")
                if isinstance(cbid, str):
                    cbid = int(cbid) if str(cbid).isdigit() else None
                topic = args.get("topic", "")
                
                out = self.execute_cross_reference(topic, current_book_id=cbid, state=state)
                formatted = [
                    {
                        "title": item["title"],
                        "author": item["author"],
                        "page": item["page"],
                        "book_id": item["book_id"],
                        "text": item["text"],
                    }
                    for item in out.get("data", [])
                ]
                return json.dumps(formatted, ensure_ascii=False)

            elif fn_name == "highlight_book_text":
                state.ui_mutation_requested = True
                text_to_find = args.get("text_to_find", "")
                color = args.get("color", "yellow")
                
                allowed = PolicyEngine.is_action_allowed("highlight", state.provenance, {"text_to_find": text_to_find, "color": color})
                trace_logger.emit("policy_decision", step=state.current_round, tool_name=fn_name, allowed=allowed, provenance=state.provenance, payload={"text_to_find": text_to_find, "color": color}, round_num=state.current_round)
                if not allowed:
                    return json.dumps({
                        "status": "blocked",
                        "message": "Destaque visual bloqueado pelo Policy Engine (dados inseguros da web)."
                    })

                color_map = {
                    "yellow": "#fbbf24",
                    "green": "#34d399",
                    "red": "#f87171",
                    "blue": "#60a5fa",
                    "pink": "#f472b6",
                }
                hex_color = color_map.get(color, color_map["yellow"])
                if ui_mutation_callback and text_to_find:
                    ui_mutation_callback("highlight", {
                        "text_to_find": text_to_find,
                        "color": hex_color,
                        "book_id": book_id,
                    })
                    return json.dumps({
                        "status": "success",
                        "message": f"Texto '{text_to_find[:50]}...' destacado em {color} na página atual."
                    })
                else:
                    return json.dumps({
                        "status": "skipped",
                        "message": "Destaque visual indisponível (sem livro aberto ou texto vazio)."
                    })

            elif fn_name == "create_ai_bookmark":
                state.ui_mutation_requested = True
                note = args.get("note", "")
                
                allowed = PolicyEngine.is_action_allowed("bookmark", state.provenance, {"note": note})
                trace_logger.emit("policy_decision", step=state.current_round, tool_name=fn_name, allowed=allowed, provenance=state.provenance, payload={"note": note}, round_num=state.current_round)
                if not allowed:
                    return json.dumps({
                        "status": "blocked",
                        "message": "Marcador de página bloqueado pelo Policy Engine (dados inseguros da web)."
                    })

                if ui_mutation_callback and note:
                    ui_mutation_callback("bookmark", {
                        "note": note,
                        "book_id": book_id,
                    })
                    return json.dumps({
                        "status": "success",
                        "message": f"Marcador criado com a nota: '{note[:80]}...'"
                    })
                else:
                    return json.dumps({
                        "status": "skipped",
                        "message": "Marcador indisponível (sem livro aberto ou nota vazia)."
                    })

            else:
                return json.dumps({"error": f"Ferramenta '{fn_name}' desconhecida."})

        except Exception as exc:
            logger.error("Erro na execução da ferramenta '%s': %s", fn_name, exc)
            state.add_error("ToolExecutionError", str(exc))
            trace_logger.emit("error", step=state.current_round, error_type="ToolExecutionError", error_message=str(exc), tool_name=fn_name, round_num=state.current_round)
            return json.dumps({"error": f"A ferramenta falhou: {str(exc)}"})

    def query_rag(
        self,
        question: str,
        n_context: Optional[int] = None,
        book_id: Optional[int] = None,
        ui_mutation_callback: Optional[callable] = None,
    ) -> Generator[str, None, None]:
        """Pipeline RAG Agentic com streaming de tokens e controle por AgentState + PolicyEngine."""
        # Limpa qualquer sinal de cancelamento remanescente de uma operação anterior.
        # O engine é singleton; sem este reset, um único "Stop" deixaria toda query
        # seguinte abortando imediatamente até reiniciar o aplicativo.
        self.engine.reset_cancel()
        session_id = str(uuid.uuid4())
        trace_logger = TraceLogger(session_id)
        trace_logger.emit("query_started", step=0, query=question, book_id=book_id)

        if not self.engine.is_ollama_available():
            err_msg = "Ollama não está disponível. Inicie o daemon com 'ollama serve'."
            trace_logger.emit("error", step=0, error_type="RuntimeError", error_message=err_msg)
            trace_logger.emit("query_completed", step=1, error_message=err_msg)
            raise RuntimeError(err_msg)

        n = n_context or self.engine._n_context
        
        try:
            similar = self.engine.search_similar(question, n_results=n, book_id=book_id)
        except Exception as e:
            try:
                hits = self.engine.keyword_search_db(question, book_id=book_id)
                similar = [
                    {
                        "document": h.get("text", ""),
                        "metadata": {
                            "title": h.get("title", ""),
                            "author": h.get("author", ""),
                            "page_number": h.get("page", 1) - 1,
                            "book_id": h.get("book_id"),
                        }
                    }
                    for h in hits
                ]
            except Exception:
                similar = []

        if not similar:
            err_msg = "Nenhum documento foi encontrado na biblioteca indexada. Indexe seus livros primeiro usando o botão 'Reindexar Biblioteca'."
            trace_logger.emit("error", step=1, error_type="EmptyContext", error_message=err_msg)
            trace_logger.emit("query_completed", step=2, error_message=err_msg)
            yield err_msg
            return

        context_parts = []
        for item in similar:
            meta = item["metadata"]
            title = meta.get("title", "Sem título")
            author = meta.get("author", "")
            page_num = meta.get("page_number", 0)
            page_str = f"p. {page_num + 1}"
            header = f"[{title} — {author}, {page_str}]"
            context_parts.append(f"{header}\n{item['document']}")

        context = "\n\n".join(context_parts)
        trace_logger.emit("context_loaded", step=1, payload={"context_length": len(context), "documents_found": len(similar)})

        from src.core.rag_engine import _FIXED_SYSTEM_PROMPT, _TOOLS_DEF
        # Memória por livro: injeta os turnos recentes antes da pergunta atual,
        # permitindo perguntas de acompanhamento ("e por quê?", "dá um exemplo").
        history = self.engine.get_chat_history(book_id) if hasattr(self.engine, "get_chat_history") else []
        messages = [
            {"role": "system", "content": _FIXED_SYSTEM_PROMPT},
            {"role": "system", "content": f"Ferramentas Disponíveis (JSON Schema):\n{json.dumps(_TOOLS_DEF, ensure_ascii=False)}"},
            {"role": "system", "content": f"--- CONTEXTO ATUAL ---\n{context}\n--- FIM DO CONTEXTO ---"},
            *history,
            {"role": "user", "content": question},
        ]

        answer_acc: list[str] = []
        state = AgentState(session_id=session_id, max_rounds=5, max_time_ms=25000)

        while state.is_budget_ok():
            state.current_round += 1

            # Streaming real: consome a resposta do Ollama token a token. Conteúdo
            # textual é repassado imediatamente (TTFT real, sem atraso artificial);
            # eventuais tool_calls são acumulados ao longo da stream.
            content_parts: list[str] = []
            tool_calls: list = []
            done_reason = ""
            answer_streaming_started = False
            try:
                with self._call_chat_api(messages, stream=True, temperature=0.1) as resp:
                    for line in resp:
                        if self.engine._cancelled:
                            trace_logger.emit("early_exit", step=state.current_round, reason="cancelled")
                            trace_logger.emit("query_completed", step=state.current_round + 1, reason="cancelled")
                            return
                        if not line:
                            continue
                        try:
                            chunk = json.loads(line.decode("utf-8"))
                        except (json.JSONDecodeError, AttributeError, UnicodeDecodeError):
                            continue

                        msg = chunk.get("message", {}) or {}
                        if msg.get("tool_calls"):
                            tool_calls.extend(msg["tool_calls"])

                        token = msg.get("content", "")
                        # Só transmite conteúdo enquanto a rodada não for de ferramenta.
                        if token and not tool_calls:
                            if not answer_streaming_started:
                                trace_logger.emit("final_answer_started", step=state.current_round, round_num=state.current_round)
                                answer_streaming_started = True
                            content_parts.append(token)
                            answer_acc.append(token)
                            yield token

                        if chunk.get("done"):
                            done_reason = chunk.get("done_reason", "")
                            break
            except Exception as exc:
                err_msg = f"Falha ao contactar o assistente: {exc}"
                trace_logger.emit("error", step=state.current_round, error_type="LLMError", error_message=err_msg, round_num=state.current_round)
                trace_logger.emit("query_completed", step=state.current_round + 1, error_message=err_msg)
                yield f"\n⚠️ {err_msg}"
                return

            content = "".join(content_parts)

            # Caso 1: resposta final (sem chamadas de ferramenta) — já foi transmitida.
            if not tool_calls:
                if answer_streaming_started:
                    trace_logger.emit("final_answer_completed", step=state.current_round, round_num=state.current_round, payload={"length": len(content)})

                # Tratamento de continuação (resposta truncada por limite de tokens)
                if done_reason == "length" and getattr(state, "continuation_count", 0) < 1:
                    state.continuation_count = getattr(state, "continuation_count", 0) + 1
                    messages.append({"role": "assistant", "content": content})
                    messages.append({"role": "user", "content": "Continue exatamente de onde parou."})
                    logger.info("Continuação transparente acionada no round %d", state.current_round)
                    continue  # Nova chamada no loop while budget_ok

                # Memória por livro: grava o turno concluído.
                if hasattr(self.engine, "append_chat_turn"):
                    self.engine.append_chat_turn(book_id, question, "".join(answer_acc))

                payload = {
                    "sources_used": list(state.sources_used),
                    "books_consulted": list(state.books_consulted),
                    "repeated_result_count": state.repeated_result_count,
                    "errors": state.errors,
                    "web_seen": state.web_seen,
                    "ui_mutation_requested": state.ui_mutation_requested,
                    "called_tools": state.called_tools
                }
                trace_logger.emit("query_completed", step=state.current_round + 1, payload=payload)
                return

            # Caso 2: o modelo solicitou ferramentas nesta rodada.
            messages.append({"role": "assistant", "content": content, "tool_calls": tool_calls})
            round_outputs = []

            for tool_call in tool_calls:
                if self.engine._cancelled:
                    trace_logger.emit("early_exit", step=state.current_round, reason="cancelled")
                    trace_logger.emit("query_completed", step=state.current_round + 1, reason="cancelled")
                    return

                fn = tool_call.get("function", {})
                fn_name = fn.get("name", "")
                args = fn.get("arguments", {})
                if isinstance(args, str):
                    try:
                        args = json.loads(args)
                    except json.JSONDecodeError:
                        args = {}

                yield f"\n[⚙️ {fn_name}(...)…]\n"

                tool_result_str = self._execute_tool_orchestrated(
                    fn_name,
                    args,
                    state,
                    trace_logger,
                    book_id=book_id,
                    ui_mutation_callback=ui_mutation_callback
                )
                trace_logger.emit("tool_call_completed", step=state.current_round, tool_name=fn_name, round_num=state.current_round, payload={"result": tool_result_str})
                messages.append({"role": "tool", "content": tool_result_str})

                round_outputs.append(create_tool_output(
                    status="success" if "error" not in tool_result_str else "error",
                    data=[{"raw_result": tool_result_str}],
                    provenance="web" if fn_name == "search_web" else "local"
                ))

            digest = self.compute_results_digest(round_outputs)
            if state.last_result_hash and state.last_result_hash == digest:
                state.repeated_result_count += 1
                logger.info("Early-Exit ativado no loop de streaming (rodada %d).", state.current_round)
                trace_logger.emit("early_exit", step=state.current_round, reason="resultados_identicos", round_num=state.current_round)
                break

            state.last_result_hash = digest

        yield "\n[⚠️ Limite de rodadas de ferramentas atingido — gerando resposta final...]\n"
        trace_logger.emit("early_exit", step=state.current_round, reason="max_rounds_reached", round_num=state.current_round)
        trace_logger.emit("final_answer_started", step=state.current_round, round_num=state.current_round)
        try:
            with self._call_chat_api(messages, stream=True) as resp:
                accumulated_content = []
                for line in resp:
                    if self.engine._cancelled:
                        trace_logger.emit("early_exit", step=state.current_round, reason="cancelled")
                        trace_logger.emit("query_completed", step=state.current_round + 1, reason="cancelled")
                        return
                    if not line:
                        continue
                    try:
                        chunk = json.loads(line.decode("utf-8"))
                        token = chunk.get("message", {}).get("content", "")
                        if token:
                            accumulated_content.append(token)
                            yield token
                        if chunk.get("done", False):
                            done_reason = chunk.get("done_reason", "")
                            trace_logger.emit("final_answer_completed", step=state.current_round, round_num=state.current_round)
                            if done_reason == "length" and getattr(state, "continuation_count", 0) < 1:
                                state.continuation_count = getattr(state, "continuation_count", 0) + 1
                                yield "\n[⚠️ A resposta foi interrompida pelo limite de tokens. Retomando...]\n"
                                messages.append({"role": "assistant", "content": "".join(accumulated_content)})
                                messages.append({"role": "user", "content": "Continue exatamente de onde parou."})
                                try:
                                    with self._call_chat_api(messages, stream=True) as resp_cont:
                                        for line_cont in resp_cont:
                                            if not line_cont: continue
                                            try:
                                                c = json.loads(line_cont.decode("utf-8"))
                                                t = c.get("message", {}).get("content", "")
                                                if t: yield t
                                            except json.JSONDecodeError: continue
                                except Exception:
                                    pass
                            if hasattr(self.engine, "append_chat_turn"):
                                self.engine.append_chat_turn(book_id, question, "".join(accumulated_content))
                            trace_logger.emit("query_completed", step=state.current_round + 1)
                            return
                    except json.JSONDecodeError:
                        continue
        except Exception as exc:
            err_msg = f"Falha ao gerar resposta final: {exc}"
            trace_logger.emit("error", step=state.current_round, error_type="LLMError", error_message=err_msg)
            trace_logger.emit("query_completed", step=state.current_round + 1, error_message=err_msg)
            yield f"\n⚠️ {err_msg}"
