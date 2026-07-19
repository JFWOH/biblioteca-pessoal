"""Lógica pura de estatísticas de leitura (streak, série semanal).

Sem PyQt6, sem SQLite (ADR-006) — recebe listas/dicts já carregados pelo
``LibraryDB`` e devolve valores agregados. Mantido separado para ser
testável sem tocar em disco (Tarefa 5.2).
"""

from datetime import date, timedelta

# Teto anti-idle por página (segundos): tempo acima disso numa única página
# quase certamente é o leitor ausente (foi tomar café com o livro aberto),
# não leitura ativa. 300s (5 min) é generoso para uma página densa de texto
# e ainda corta a distorção de horas de idle — mesma ordem de grandeza usada
# por apps de leitura com tracking de tempo.
MAX_SESSION_SECONDS_PER_PAGE = 300


def clamp_session_seconds(elapsed: float, cap: int = MAX_SESSION_SECONDS_PER_PAGE) -> int:
    """Normaliza o tempo decorrido numa página para registro em sessão.

    Regras: negativo/NaN → 0 (relógio nunca volta; entrada inválida não
    registra); acima de ``cap`` → ``cap`` (anti-idle, ver
    ``MAX_SESSION_SECONDS_PER_PAGE``). Devolve segundos inteiros.
    """
    try:
        value = float(elapsed)
    except (TypeError, ValueError):
        return 0
    if value != value or value <= 0:  # NaN ou não-positivo
        return 0
    return int(min(value, cap))


def total_elapsed_seconds(accumulated: float, started_at: float | None,
                          now: float) -> float:
    """Soma o tempo já acumulado (de pausas anteriores, ex.: janela
    minimizada) com o trecho em curso, se houver cronômetro rodando.

    Pura — recebe ``now`` já capturado pelo chamador (``time.monotonic()``
    mora na GUI, nunca no core; ADR-006). Usada tanto para PAUSAR (o trecho
    em curso é congelado no acumulado, sem aplicar teto ainda) quanto para
    CONSUMIR o total ao trocar de página/fechar o livro (o teto anti-idle é
    responsabilidade de ``clamp_session_seconds`` no ponto de consumo final
    — aplicá-lo aqui, por trecho, permitiria burlar o cap de
    ``MAX_SESSION_SECONDS_PER_PAGE`` pausando e retomando repetidamente).
    ``started_at`` no futuro (relógio nunca deveria regredir, mas por
    segurança) não gera trecho negativo.
    """
    running = max(0.0, now - started_at) if started_at is not None else 0.0
    return accumulated + running


def compute_reading_streak(read_dates, today: str | None = None) -> int:
    """Dias consecutivos com leitura registrada, terminando hoje OU ontem.

    ``read_dates``: iterável de datas (``"YYYY-MM-DD"``) que tiveram pelo
    menos 1 segundo de leitura somado em ``reading_sessions``.

    Regra do streak: se hoje ainda não teve nenhuma sessão registrada, o
    streak NÃO zera imediatamente — ele continua contando a partir de ontem
    (o usuário pode não ter lido ainda hoje). Só quebra quando um dia INTEIRO
    se passa sem nenhuma sessão (nem hoje, nem ontem têm leitura).

    ``today`` é injetável (``"YYYY-MM-DD"``) para testabilidade; por padrão
    usa a data local do sistema (``date.today()``).
    """
    dates = set(read_dates)
    today_d = date.fromisoformat(today) if today else date.today()
    if today_d.isoformat() in dates:
        cursor = today_d
    elif (today_d - timedelta(days=1)).isoformat() in dates:
        cursor = today_d - timedelta(days=1)
    else:
        return 0

    streak = 0
    while cursor.isoformat() in dates:
        streak += 1
        cursor -= timedelta(days=1)
    return streak


def compute_weekly_minutes(sessions, weeks: int = 8, today: str | None = None) -> list[dict]:
    """Minutos lidos por semana ISO, das últimas ``weeks`` semanas.

    ``sessions``: lista de dicts com ``date`` (``"YYYY-MM-DD"``) e
    ``seconds``. Devolve uma lista ordenada da semana mais ANTIGA para a mais
    RECENTE (a última entrada é sempre a semana corrente — útil para o card
    "Esta semana" ler ``resultado[-1]``). Semanas sem nenhuma sessão aparecem
    com ``minutes=0`` (nunca faltam da lista) para o gráfico manter o eixo
    fixo em ``weeks`` colunas.

    Cada item: ``{"week": "2026-W29", "label": "S29", "minutes": int}``.
    """
    today_d = date.fromisoformat(today) if today else date.today()

    order: list[tuple[int, int]] = []
    buckets: dict[tuple[int, int], int] = {}
    for i in range(weeks - 1, -1, -1):
        d = today_d - timedelta(weeks=i)
        iso_year, iso_week, _ = d.isocalendar()
        key = (iso_year, iso_week)
        if key not in buckets:
            buckets[key] = 0
            order.append(key)

    for row in sessions:
        try:
            d = date.fromisoformat(row["date"])
        except (KeyError, ValueError, TypeError):
            continue
        iso_year, iso_week, _ = d.isocalendar()
        key = (iso_year, iso_week)
        if key in buckets:
            buckets[key] += int(row.get("seconds") or 0)

    return [
        {"week": f"{y}-W{w:02d}", "label": f"S{w:02d}", "minutes": buckets[(y, w)] // 60}
        for (y, w) in order
    ]
