# Relatório de Baseline do TTS
## Fase 13B.2 — Real Kokoro Validation & Path Trace

---

## 1. Resumo Executivo

Este relatório apresenta os resultados obtidos durante a validação em runtime real do subsistema de áudio/TTS da **Biblioteca Pessoal Inteligente** sob o ambiente de baseline provisório degradado (Kokoro executando em CPU).

---

## 2. Resultados da Validação Real

A validação foi realizada executando o script dedicado `scratch/validate_kokoro.py` na venv local. Os logs capturaram os tempos de inicialização e a integridade da conversão do texto em áudio.

### Métricas Coletadas

| Parâmetro | Tempo Observado | Descrição / Significado |
|---|---|---|
| **Tempo de Importação** | `3.0749s` | Tempo total para importar os pacotes `kokoro` e `torch`. |
| **Warmup do Pipeline** | `1.8141s` | Tempo para o `KPipeline("p")` se carregar em memória e rodar a inferência inicial (warmup de 1 caractere). |
| **Inference/TTFB (1º Chunk)** | `1.6907s` | Tempo para sintetizar o texto de 90 caracteres (`Olá! Este é um teste...`) e retornar o primeiro bloco de áudio. |
| **Dispositivo de Runtime** | `cpu` | Dispositivo de hardware mapeado e utilizado pelo PyTorch. |
| **Volume de Áudio** | `238.140 frames` | Frames de áudio em float32 a 44.1kHz (após resampling do ContinuousPlayer). |

---

## 3. Classificação Formal do Estado do Kokoro

Com base nas evidências materiais coletadas do runtime, classificamos o estado do Kokoro da seguinte forma:

> [!WARNING]
> **Classificação:** `funcional, porém degradado`
>
> *   **Razão:** O modelo está importável, possui cache local de pesos 100% íntegro (materializado), inicializa com sucesso e gera áudio real legível. No entanto, é forçado a rodar em CPU devido à ausência de kernels para Blackwell (`sm_120`) na build atual estável do PyTorch, resultando em latência e warmup de categoria elevada (latência reportada como `high`).

---

## 4. TTSRouter Path Trace (Provider Final)

Durante a síntese do texto de teste:
1. **Provider Preferido:** `kokoro` (definido no perfil de voz do livro).
2. **Provider Selecionado pelo Roteador:** `Kokoro` (registrado como healthy=True).
3. **Warmup Event check:** O roteador detectou `is_ready=True` (warmup de 1.81s já havia sido concluído).
4. **Análise de SLO de TTFB:**
   *   O tempo do primeiro bloco de áudio gerado (TTFB) foi de **1,69 segundos**.
   *   O SLO limite estabelecido no projeto é de **3,00 segundos**.
   *   **Resultado:** Como $1,69\text{s} < 3,00\text{s}$, a restrição do SLO de latência foi totalmente atendida.
5. **Acionamento de Fallback:** Não ocorreu fallback (o provimento não degradou para Piper ou pyttsx3).
6. **Provider Efetivamente Utilizado:** `Kokoro` (confirmado pelo log final da chamada speak: `Spoke 1/1 chunks using 'Kokoro'`).

---

## 5. Logs Estruturados da Execução

Abaixo estão transcritos os logs literais extraídos da validação real do roteador:
```
2026-06-15 00:21:24,157 [WARNING] src.core.tts.kokoro_provider: KOKORO: CUDA device capability sm_120 is not supported by current PyTorch installation (supported: ['sm_50', 'sm_60', 'sm_61', 'sm_70', 'sm_75', 'sm_80', 'sm_86', 'sm_90']). Forcing CPU device to prevent crashes/warnings.
2026-06-15 00:21:24,157 [INFO] src.core.tts.tts_router: TTS_ROUTER: Registered provider 'kokoro' (tier B)
2026-06-15 00:21:24,157 [INFO] src.core.tts.kokoro_provider: KOKORO_WARMUP_STARTED: Background pre-warm started for language 'p'
2026-06-15 00:21:25,618 [INFO] src.core.tts.kokoro_provider: KOKORO: Pipeline for 'p' loaded successfully
2026-06-15 00:21:25,619 [INFO] src.core.tts.kokoro_provider: KOKORO_PIPELINE_LOAD_FINISHED: Kokoro pipeline loaded in 1458.52 ms.
2026-06-15 00:21:25,971 [INFO] src.core.tts.kokoro_provider: KOKORO_WARMUP_FINISHED: Warmup inference finished.
2026-06-15 00:21:25,971 [INFO] src.core.tts.kokoro_provider: KOKORO_WARMUP_MS: 352.29 ms
2026-06-15 00:21:25,971 [INFO] src.core.tts.kokoro_provider: KOKORO_READY: Kokoro is ready for synthesis.
2026-06-15 00:21:25,974 [INFO] src.core.tts.tts_router: PROVIDER_SELECTED_REASON: Preferred was 'kokoro', selected 'Kokoro'
2026-06-15 00:21:25,974 [INFO] src.core.tts.tts_router: ACTIVE_PROVIDER: Kokoro
2026-06-15 00:21:27,667 [INFO] src.core.tts.tts_router: TTS_ROUTER_TTFB_MS: 1690.69 ms (first segment of stream)
2026-06-15 00:21:27,682 [INFO] src.core.tts.tts_router: TTS_ROUTER: Spoke 1/1 chunks using 'Kokoro'
```

---

## 6. Conclusões e Recomendações

*   O pipeline TTS está totalmente operacional.
*   A execução em CPU é estável e não compromete a integridade do áudio, além de cumprir o SLO de 3 segundos em tarefas isoladas.
*   *Recomendação:* Para o uso em tempo real na interface gráfica com livros densos, o warmup assíncrono em background (que já está implementado no `AudioWorker`) é essencial para evitar o travamento inicial da interface visual.
