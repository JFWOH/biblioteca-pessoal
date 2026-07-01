# Registro de Riscos Remanescentes
## Fase 13B.2 — Risk Register

---

## 1. Mapeamento de Riscos Atuais

Este documento identifica os riscos remanescentes do sistema no final da Fase 13B.2, especificamente em relação ao ambiente TTS, hardware e suíte de testes.

---

## 2. Tabela de Riscos Remanescentes

| ID | Risco | Impacto | Probabilidade | Mitigação Aplicada / Recomendada | Status |
|---|---|---|---|---|---|
| **R-01** | **Violação do SLO de TTFB do Kokoro na primeira inicialização (CPU)** | 🟡 Médio | 🔴 Alta | Warmup assíncrono em background ativado na GUI (`AudioWorker`). A primeira chamada é amortecida pela thread de background, evitando travamento da interface. | 🟢 Monitorado |
| **R-02** | **Incompatibilidade Blackwell (`sm_120`) com PyTorch Estável** | 🟡 Médio | 🔴 Alta | Manter a execução em CPU como baseline degradada padrão. Documentar a receita experimental de atualização da build para PyTorch Nightly com CUDA 12.8 no runbook do projeto. | 🟢 Controlado |
| **R-03** | **Falha no driver de som físico ou travamento do `sounddevice`** | 🔴 Alto | 🟢 Baixa | O `ContinuousAudioPlayer` detecta a indisponibilidade do `sounddevice` em runtime e realiza fallback automático para comandos de OS nativos (`winsound`/`aplay`/`afplay`). | 🟢 Mitigado |
| **R-04** | **Consumo elevado de CPU por síntese concorrente** | 🟡 Médio | 🟡 Média | O `TTSRouter` segmenta e chunkifica o texto antes do envio ao backend, limitando o tamanho de caracteres processados por lote e minimizando o pico de uso do processador. | 🟢 Mitigado |
| **R-05** | **Flutuações de IO e travamento de concorrência no SQLite** | 🔴 Alto | 🟢 Baixa | Hardening aplicado na Fase 13B (conexões thread-local e single-writer lock ativo em `tests/test_concurrency.py`). | 🟢 Mitigado |

---

## 3. Matriz de Severidade

```
        PROBABILIDADE
        Alta      | R-01, R-02  |             |
        Média     |             | R-04        |
        Baixa     |             |             | R-03, R-05
                  +-------------+-------------+-------------
                      Baixo         Médio         Alto
                                  IMPACTO
```

---

## 4. Plano de Contingência para Falha Crítica de Áudio

Caso o hardware de som local sofra pane ou seja bloqueado por outro processo:
1. O worker de áudio da GUI captura a exception e exibe uma mensagem de status sem travar a interface visual.
2. O usuário pode pausar, resetar o player (limpando a fila de reprodução) e tentar novamente.
3. Se necessário, o aplicativo pode ser reiniciado para liberar travas sob o SAPI5 (Windows).
