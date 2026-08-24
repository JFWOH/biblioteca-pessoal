"""TTFB da narração Kokoro no nível do provider (Onda P — rodada UX ago/2026).

Mede duas coisas distintas, que o SLO de 3,0s do ``tts_router`` mistura:

    init_s          ``KokoroProvider.initialize()`` até o warmup terminar
                    (carga do pipeline + inferência de aquecimento)
    ttfb_warm_ms    tempo até o PRIMEIRO chunk de áudio de ``synthesize_stream``
                    com o provider JÁ aquecido

Nunca baixa nada: ``HF_HUB_OFFLINE=1`` e, se o modelo não estiver materializado
no cache local do Hugging Face, o script reporta ``skip=<motivo>`` e sai com 0.

Baseline jul/2026: TTFB warm em GPU = 148,64ms (RTX 5060 Ti).

Uso:
    venv\\Scripts\\python.exe tools/perf/measure_tts_ttfb.py [--rodadas 3]
"""

from __future__ import annotations

import argparse
import os
import sys
import time
from pathlib import Path

# Antes de qualquer import do projeto: nada de rede nesta medição.
os.environ["HF_HUB_OFFLINE"] = "1"
os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")
sys.path.insert(0, str(Path(__file__).resolve().parents[2]))

from tools.perf._common import emit, fmt, median  # noqa: E402

FRASE = "A leitura transforma o silêncio em pensamento."


def _skip(motivo: str) -> int:
    emit("medicao", "tts_ttfb")
    emit("skip", motivo)
    return 0


def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__,
                                 formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--rodadas", type=int, default=3,
                    help="medições de TTFB com o provider quente. Padrão: 3")
    ap.add_argument("--voz", default="pf_dora", help="voice_id. Padrão: pf_dora")
    ap.add_argument("--timeout-init", type=float, default=180.0,
                    help="limite de espera pelo warmup, em segundos. Padrão: 180")
    args = ap.parse_args()

    try:
        from src.core.tts.base_tts_provider import TTSProviderUnavailable
        from src.core.tts.kokoro_provider import (
            KokoroProvider,
            check_kokoro_cache_materialized,
        )
    except Exception as e:
        return _skip(f"import_falhou:{type(e).__name__}:{e}")

    if not check_kokoro_cache_materialized():
        return _skip("cache_hf_do_kokoro_nao_materializado (offline: nada foi baixado)")

    try:
        provider = KokoroProvider()
    except TTSProviderUnavailable as e:
        return _skip(f"provider_indisponivel:{e}")
    except Exception as e:
        return _skip(f"provider_erro:{type(e).__name__}:{e}")

    emit("medicao", "tts_ttfb")
    emit("provider", provider.name)
    emit("device", getattr(provider, "_device", "?"))
    emit("latency_profile", provider.latency_profile())
    emit("cache_hit", provider.model_cache_hit or check_kokoro_cache_materialized())

    t0 = time.perf_counter()
    provider.initialize()
    pronto = provider._warmup_event.wait(timeout=args.timeout_init)
    init_s = time.perf_counter() - t0
    emit("init_s", fmt(init_s, 2))
    emit("warmup_concluiu", bool(pronto))

    if not provider.is_ready:
        return _skip(f"warmup_falhou:{provider.last_warmup_error or 'motivo desconhecido'}")

    ttfbs: list[float] = []
    for i in range(args.rodadas):
        t = time.perf_counter()
        primeiro_ms: float | None = None
        erro: str | None = None
        gerador = provider.synthesize_stream(FRASE, voice_id=args.voz)
        try:
            for resultado in gerador:
                if getattr(resultado, "error", None):
                    erro = resultado.error
                    break
                if getattr(resultado, "audio_data", None) is not None:
                    primeiro_ms = (time.perf_counter() - t) * 1000.0
                    break
        finally:
            gerador.close()

        if erro:
            emit(f"rodada{i + 1}_erro", erro)
            continue
        if primeiro_ms is None:
            emit(f"rodada{i + 1}_erro", "nenhum_chunk_de_audio")
            continue
        ttfbs.append(primeiro_ms)
        emit(f"rodada{i + 1}_ttfb_ms", fmt(primeiro_ms, 2))

    if not ttfbs:
        return _skip("nenhuma_rodada_de_ttfb_bem_sucedida")

    # A 1ª síntese após o warmup ainda paga inicialização preguiçosa (CUDA,
    # grafo, voz), então ela é reportada à parte e fica fora da mediana "warm" —
    # é ela, porém, que o usuário sente na primeira frase da narração.
    quentes = ttfbs[1:] if len(ttfbs) > 1 else ttfbs
    emit("ttfb_primeira_ms", fmt(ttfbs[0], 2))
    emit("ttfb_warm_ms", fmt(median(quentes), 2))
    emit("ttfb_warm_ms_todas", ",".join(fmt(v, 2) for v in quentes))
    emit("frase", FRASE)
    emit("baseline_jul_ttfb_warm_gpu_ms", "148.64")

    provider.shutdown()
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
