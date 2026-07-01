import json
from datetime import datetime
from pathlib import Path

def parse_iso_timestamp(ts_str: str) -> datetime:
    # Lida com +00:00 ou Z
    if ts_str.endswith("Z"):
        ts_str = ts_str[:-1] + "+00:00"
    return datetime.fromisoformat(ts_str)

def extract_metrics(traces_dir: Path) -> dict:
    metrics = {
        "total_sessions": 0,
        "total_steps": 0,
        "total_rounds": 0,
        "fallback_count": 0,
        "policy_allowed": 0,
        "policy_blocked": 0,
        "web_searches": 0,
        "session_durations": [],
        "errors": 0,
    }

    for file_path in traces_dir.glob("trace_*.jsonl"):
        # Ignorar traces dummy usados em testes de retenção
        if file_path.name.startswith("trace_dummy_"):
            continue

        events = []
        with open(file_path, "r", encoding="utf-8") as f:
            for line in f:
                line = line.strip()
                if not line:
                    continue
                try:
                    events.append(json.loads(line))
                except json.JSONDecodeError:
                    pass

        if not events:
            continue

        metrics["total_sessions"] += 1
        metrics["total_steps"] += len(events)

        start_time = None
        end_time = None
        rounds_in_session = 0

        for e in events:
            etype = e.get("event_type")
            ts = e.get("timestamp")
            
            if etype == "query_started":
                start_time = parse_iso_timestamp(ts)
            elif etype == "query_completed":
                end_time = parse_iso_timestamp(ts)
            elif etype == "fallback_activated":
                metrics["fallback_count"] += 1
            elif etype == "policy_decision":
                if e.get("allowed", True):
                    metrics["policy_allowed"] += 1
                else:
                    metrics["policy_blocked"] += 1
            elif etype == "tool_call_requested":
                if e.get("tool_name") == "search_web":
                    metrics["web_searches"] += 1
            elif etype == "final_answer_started":
                rounds_in_session = max(rounds_in_session, e.get("round", 0))
            elif etype == "error":
                metrics["errors"] += 1

        metrics["total_rounds"] += rounds_in_session

        if start_time and end_time:
            duration = (end_time - start_time).total_seconds()
            metrics["session_durations"].append(duration)

    return metrics

def display_metrics(metrics: dict):
    print("=" * 60)
    print("MÉTRICAS DE DESEMPENHO E ESTABILIDADE (RAG LOCAL)")
    print("=" * 60)
    print(f"Total de Sessões Analisadas:      {metrics['total_sessions']}")
    
    if metrics['total_sessions'] > 0:
        avg_steps = metrics['total_steps'] / metrics['total_sessions']
        avg_rounds = metrics['total_rounds'] / metrics['total_sessions']
        print(f"Média de Eventos (Steps) / Sessão: {avg_steps:.2f}")
        print(f"Média de Rodadas (Rounds) / Sessão: {avg_rounds:.2f}")
    else:
        print("Média de Eventos (Steps) / Sessão: N/A")
        print("Média de Rodadas (Rounds) / Sessão: N/A")

    print(f"Ativações de Fallback RAG:         {metrics['fallback_count']}")
    print(f"Total de Pesquisas Web (DDG):      {metrics['web_searches']}")
    print(f"Decisões da Policy (Permitidas):   {metrics['policy_allowed']}")
    print(f"Decisões da Policy (Bloqueadas):   {metrics['policy_blocked']}")
    print(f"Exceções / Erros de Execução:      {metrics['errors']}")

    if metrics['session_durations']:
        avg_duration = sum(metrics['session_durations']) / len(metrics['session_durations'])
        max_duration = max(metrics['session_durations'])
        min_duration = min(metrics['session_durations'])
        print(f"Latência de Resposta RAG (Média):  {avg_duration:.2f} segundos")
        print(f"Latência de Resposta RAG (Mín):    {min_duration:.2f} segundos")
        print(f"Latência de Resposta RAG (Máx):    {max_duration:.2f} segundos")
    else:
        print("Latência de Resposta RAG (Média):  N/A")

    print("=" * 60)

if __name__ == "__main__":
    import argparse
    parser = argparse.ArgumentParser(description="Extração de Métricas Locais de Traces.")
    parser.add_argument("--dir", type=str, default="data/traces", help="Diretório de traces.")
    args = parser.parse_args()

    traces_path = Path(args.dir)
    if not traces_path.is_absolute():
        base_dir = Path(__file__).resolve().parent.parent.parent
        traces_path = base_dir / args.dir

    if traces_path.exists():
        metrics = extract_metrics(traces_path)
        display_metrics(metrics)
    else:
        print(f"Diretório de traces não encontrado: {traces_path}")
