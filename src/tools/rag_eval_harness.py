import argparse
from pathlib import Path

from src.tools.trace_inspector import parse_trace_file

UI_MUTATION_TOOLS = {"highlight_book_text", "create_ai_bookmark"}

def evaluate_session(events: list[dict]) -> dict:
    """
    Avalia a sanidade estrutural de uma sessão de trace e classifica a qualidade semântica.
    """
    anomalies = []
    classification = "healthy"
    
    if not events:
        return {"anomalies": ["Trace vazio ou não pôde ser parseado."], "classification": "error_controlled"}
        
    first_event = events[0].get("event_type")
    last_event = events[-1].get("event_type")
    
    if first_event != "query_started":
        anomalies.append(f"Trace não começa com 'query_started'. Começa com: {first_event}")
        
    valid_endings = {"query_completed", "early_exit"}
    
    # Variáveis de métricas para classificação
    has_error = False
    fallback_count = 0
    repeated_result_count = 0
    ui_requests = 0
    policy_decisions = 0
    web_seen = False
    has_local_sources = False
    
    # Se o ultimo nao for um ending valido, e nao houver um "error" terminal, é uma anomalia
    if last_event not in valid_endings and last_event != "error":
        # as vezes o error nao e o ultimo, mas a query termina de forma abrupta.
        # checamos se houve error.
        has_error = any(e.get("event_type") == "error" for e in events)
        if not has_error:
            anomalies.append(f"Trace não possui finalização válida. Terminou com: {last_event}")
            
    # Checar se toda requisição de UI Mutation teve uma policy decision pareada (logo em seguida ou no mesmo step/step+1)
    # A lógica aqui é simples: conta requisições e conta decisões. Deveriam ser consistentes se foi bloqueado ou autorizado.
    ui_requests = 0
    policy_decisions = 0
    
    for e in events:
        etype = e.get("event_type")
        if etype == "tool_call_requested":
            if e.get("tool_name") in UI_MUTATION_TOOLS:
                ui_requests += 1
        elif etype == "policy_decision":
            policy_decisions += 1
        elif etype == "error":
            has_error = True
        elif etype == "fallback_activated":
            fallback_count += 1
        elif etype == "early_exit":
            if e.get("reason") == "resultados_identicos":
                repeated_result_count += 1
        elif etype == "query_completed":
            payload = e.get("payload", {})
            if isinstance(payload, dict):
                repeated_result_count = max(repeated_result_count, payload.get("repeated_result_count", 0))
                web_seen = payload.get("web_seen", False)
                sources = payload.get("sources_used", [])
                if "local" in sources:
                    has_local_sources = True
            
    if ui_requests > 0 and policy_decisions == 0:
        anomalies.append(f"Detectou {ui_requests} chamadas de mutação UI sem nenhuma decisão de Policy correspondente.")
        
    if len(events) > 50:
        anomalies.append(f"Trace muito longo ({len(events)} eventos). Possível loop infinito ou recursão anormal.")
        
    # Classificação Semântica
    if ui_requests > 0 and policy_decisions == 0:
        classification = "policy_inconsistent"
    elif repeated_result_count > 0:
        classification = "redundant"
    elif fallback_count > 0:
        classification = "fallback_heavy"
    elif web_seen and not has_local_sources:
        classification = "low_local_grounding"
    elif has_error and last_event in valid_endings:
        classification = "error_controlled"
        
    return {"anomalies": anomalies, "classification": classification}

def evaluate_directory(traces_dir: Path) -> dict:
    """Avalia todos os traces do diretório."""
    results = {
        "total_evaluated": 0,
        "perfect_sessions": 0,
        "sessions_with_anomalies": 0,
        "anomalies_log": {},
        "classifications": {
            "healthy": 0,
            "redundant": 0,
            "fallback_heavy": 0,
            "policy_inconsistent": 0,
            "error_controlled": 0,
            "low_local_grounding": 0
        }
    }
    
    if not traces_dir.exists() or not traces_dir.is_dir():
        return results
        
    for file_path in traces_dir.glob("trace_*.jsonl"):
        events = parse_trace_file(file_path)
        if not events:
            continue
            
        session_id = events[0].get("session_id", file_path.stem)
        eval_res = evaluate_session(events)
        anomalies = eval_res["anomalies"]
        cls_type = eval_res.get("classification", "healthy")
        
        results["total_evaluated"] += 1
        
        # Incrementar de forma segura
        if cls_type not in results["classifications"]:
            results["classifications"][cls_type] = 0
        results["classifications"][cls_type] += 1
        
        if anomalies:
            results["sessions_with_anomalies"] += 1
            results["anomalies_log"][session_id] = anomalies
        else:
            results["perfect_sessions"] += 1
            
    return results

if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="Evaluation Harness para Traces do Agentic RAG.")
    parser.add_argument("--dir", type=str, default="data/traces", help="Diretório de traces.")
    parser.add_argument("--session", type=str, help="Avalia apenas uma sessão específica.")
    
    args = parser.parse_args()
    
    target_dir = Path(args.dir)
    if not target_dir.is_absolute():
        base_dir = Path(__file__).resolve().parent.parent.parent
        target_dir = base_dir / args.dir

    if not target_dir.exists():
        print(f"Diretório não encontrado: {target_dir}")
        exit(1)
        
    if args.session:
        file_path = target_dir / f"trace_{args.session}.jsonl"
        events = parse_trace_file(file_path)
        if not events:
            print("Sessão não encontrada ou arquivo vazio.")
            exit(1)
            
        print(f"Avaliando Sessão: {args.session}")
        eval_res = evaluate_session(events)
        anomalies = eval_res["anomalies"]
        print(f"Classificação Semântica: {eval_res['classification']}")
        if not anomalies:
            print("[OK] Estruturalmente perfeita.")
        else:
            print("[FAIL] Anomalias detectadas:")
            for a in anomalies:
                print(f"  - {a}")
    else:
        print(f"Iniciando avaliação em lote do diretório: {target_dir}")
        res = evaluate_directory(target_dir)
        print("=" * 50)
        print("RAG EVALUATION REPORT")
        print("=" * 50)
        print(f"Total avaliado:   {res['total_evaluated']}")
        print(f"Sessões perfeitas: {res['perfect_sessions']}")
        print(f"Com anomalias:    {res['sessions_with_anomalies']}")
        
        print("\nDISTRIBUIÇÃO DE CLASSIFICAÇÃO SEMÂNTICA:")
        for cls_name, count in res["classifications"].items():
            if count > 0:
                print(f"  - {cls_name}: {count}")
        
        if res['anomalies_log']:
            print("\nDETALHAMENTO DE ANOMALIAS:")
            for s_id, anoms in res['anomalies_log'].items():
                print(f"\nSessão: {s_id}")
                for a in anoms:
                    print(f"  - {a}")
                    
        if res['sessions_with_anomalies'] > 0:
            exit(1)
