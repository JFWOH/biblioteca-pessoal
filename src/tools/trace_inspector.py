import os
import json
import argparse
from pathlib import Path

def parse_trace_file(file_path: Path) -> list[dict]:
    """Lê um arquivo JSONL de trace e retorna a lista de eventos."""
    events = []
    if not file_path.exists():
        return events
    with open(file_path, "r", encoding="utf-8") as f:
        for line in f:
            line = line.strip()
            if not line:
                continue
            try:
                event = json.loads(line)
                events.append(event)
            except json.JSONDecodeError:
                pass
    return events

def summarize_session(events: list[dict]) -> dict:
    """Extrai um resumo de uma sessão a partir de seus eventos."""
    if not events:
        return {}
    
    session_id = events[0].get("session_id", "unknown")
    start_time = events[0].get("timestamp", "unknown")
    query = next((e.get("query") for e in events if e.get("event_type") == "query_started"), "unknown")
    
    event_counts = {}
    has_error = False
    has_policy = False
    has_fallback = False
    
    policy_blocks = 0
    end_reason = ""
    repeated_result_count = 0
    web_seen = False
    sources_used = []
    books_consulted = []
    called_tools = []
    
    for e in events:
        etype = e.get("event_type")
        if etype:
            event_counts[etype] = event_counts.get(etype, 0) + 1
            if etype == "error":
                has_error = True
            elif etype == "policy_decision":
                has_policy = True
                if not e.get("allowed", True):
                    policy_blocks += 1
            elif etype == "fallback_activated":
                has_fallback = True
            elif etype == "early_exit":
                end_reason = e.get("reason", "early_exit")
                if end_reason == "resultados_identicos":
                    repeated_result_count += 1
                
    end_event = events[-1]
    status = end_event.get("event_type", "incomplete")
    if not end_reason:
        end_reason = status
        
    if status == "query_completed":
        payload = end_event.get("payload", {})
        if isinstance(payload, dict):
            repeated_result_count = max(repeated_result_count, payload.get("repeated_result_count", 0))
            web_seen = payload.get("web_seen", False)
            sources_used = payload.get("sources_used", [])
            books_consulted = payload.get("books_consulted", [])
            called_tools = payload.get("called_tools", [])
    
    return {
        "session_id": session_id,
        "start_time": start_time,
        "query": query,
        "event_counts": event_counts,
        "has_error": has_error,
        "has_policy": has_policy,
        "has_fallback": has_fallback,
        "status": status,
        "end_reason": end_reason,
        "total_steps": len(events),
        "policy_blocks": policy_blocks,
        "repeated_result_count": repeated_result_count,
        "web_seen": web_seen,
        "sources_used": sources_used,
        "books_consulted": books_consulted,
        "called_tools": called_tools
    }

def get_all_summaries(traces_dir: Path) -> list[dict]:
    """Retorna o resumo de todos os traces disponíveis."""
    summaries = []
    if not traces_dir.exists() or not traces_dir.is_dir():
        return summaries
        
    for file_path in traces_dir.glob("trace_*.jsonl"):
        events = parse_trace_file(file_path)
        if events:
            summary = summarize_session(events)
            # Guardamos o arquivo no resumo
            summary["_file"] = file_path
            summaries.append(summary)
            
    # Ordenar por data (tentando usar o start_time, senao fallback p/ nome do arquivo ou path)
    summaries.sort(key=lambda x: x.get("start_time", ""), reverse=True)
    return summaries

def cmd_list(traces_dir: Path):
    summaries = get_all_summaries(traces_dir)
    print(f"Encontrados {len(summaries)} traces em {traces_dir}\n")
    print(f"{'SESSION ID':<38} | {'STATUS':<15} | {'STEPS':<5} | {'QUERY'}")
    print("-" * 80)
    for s in summaries:
        query_preview = s['query'][:35] + "..." if len(s['query']) > 35 else s['query']
        status = s['status']
        if s['has_error']:
            status = "ERROR"
        print(f"{s['session_id']:<38} | {status:<15} | {s['total_steps']:<5} | {query_preview}")

def cmd_session(traces_dir: Path, session_id: str):
    file_path = traces_dir / f"trace_{session_id}.jsonl"
    events = parse_trace_file(file_path)
    if not events:
        print(f"Sessão {session_id} não encontrada ou vazia.")
        return
        
    summary = summarize_session(events)
    print("=" * 70)
    print(f"SESSION ID : {summary['session_id']}")
    print(f"START TIME : {summary['start_time']}")
    print(f"QUERY      : {summary['query']}")
    print(f"STATUS     : {summary['status']} (Motivo: {summary['end_reason']})")
    print(f"FLAGS      : Error={summary['has_error']} | Policy={summary['has_policy']} (Blocks: {summary['policy_blocks']}) | Fallback={summary['has_fallback']}")
    print("-" * 70)
    print(f"WEB SEEN   : {summary['web_seen']}")
    print(f"SOURCES    : {', '.join(summary['sources_used']) if summary['sources_used'] else 'N/A'}")
    print(f"BOOKS      : {', '.join(summary['books_consulted']) if summary['books_consulted'] else 'N/A'}")
    print(f"TOOLS USED : {len(summary['called_tools'])} chamadas ({summary['repeated_result_count']} repetições detectadas)")
    print("=" * 70)
    print("EVENT LOG:")
    
    for e in events:
        etype = e.get("event_type", "unknown")
        step = e.get("step", "?")
        time_str = e.get("timestamp", "").split("T")[-1][:8]  # hh:mm:ss
        
        info = ""
        if etype == "tool_call_requested":
            info = f"-> {e.get('tool_name')} ({e.get('tool_args')})"
        elif etype == "policy_decision":
            info = f"-> action: {e.get('action')}, allowed: {e.get('allowed')}, reason: {e.get('reason')}"
        elif etype == "error":
            info = f"-> {e.get('error_type')}: {e.get('error_message')}"
        elif etype == "fallback_activated":
            info = f"-> to: {e.get('fallback_to')}, reason: {e.get('reason')}"
            
        print(f"[{time_str}] Step {step:<2} | {etype:<22} {info}")

def cmd_filter(traces_dir: Path, condition: str):
    summaries = get_all_summaries(traces_dir)
    filtered = []
    
    for s in summaries:
        if condition == "errors" and s["has_error"]:
            filtered.append(s)
        elif condition == "policy" and s["has_policy"]:
            filtered.append(s)
        elif condition == "fallback" and s["has_fallback"]:
            filtered.append(s)
            
    print(f"Traces filtrados por '{condition}': {len(filtered)}\n")
    if not filtered:
        return
        
    print(f"{'SESSION ID':<38} | {'STATUS':<15} | {'QUERY'}")
    print("-" * 80)
    for s in filtered:
        query_preview = s['query'][:40] + "..." if len(s['query']) > 40 else s['query']
        print(f"{s['session_id']:<38} | {s['status']:<15} | {query_preview}")

if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="Trace Inspector CLI para o RAG.")
    parser.add_argument("--dir", type=str, default="data/traces", help="Diretório de traces.")
    
    group = parser.add_mutually_exclusive_group(required=True)
    group.add_argument("--list", action="store_true", help="Lista um resumo de todas as sessões.")
    group.add_argument("--session", type=str, help="Mostra detalhes de um session_id específico.")
    group.add_argument("--errors", action="store_true", help="Filtra e lista sessões com erros.")
    group.add_argument("--policy", action="store_true", help="Filtra e lista sessões com decisões de policy.")
    group.add_argument("--fallback", action="store_true", help="Filtra e lista sessões com fallbacks ativados.")
    
    args = parser.parse_args()
    
    target_dir = Path(args.dir)
    if not target_dir.is_absolute():
        base_dir = Path(__file__).resolve().parent.parent.parent
        target_dir = base_dir / args.dir

    if not target_dir.exists():
        print(f"Diretório não encontrado: {target_dir}")
        exit(1)

    if args.list:
        cmd_list(target_dir)
    elif args.session:
        cmd_session(target_dir, args.session)
    elif args.errors:
        cmd_filter(target_dir, "errors")
    elif args.policy:
        cmd_filter(target_dir, "policy")
    elif args.fallback:
        cmd_filter(target_dir, "fallback")
