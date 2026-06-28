# Relatório de Validação — Fase 13B.1
## Release Validation & Warning Triage

**Data de execução:** 2026-06-14/15
**Ambiente:** Windows 10 (build 26200), Python 3.11.9, AMD64
**Baseline de referência:** Fase 13B (345 passed, 3 skipped, 0 failed)

---

## 1. Files Changed

**Nenhum arquivo de código em `src/` ou `tests/` foi modificado nesta fase.**

| Arquivo | Tipo | Descrição |
|---|---|---|
| `reports/phase_13b1_validation_report.md` | [NEW] | Este relatório de validação |

> Justificativa: Não foram encontrados warnings internos do projeto que demandassem correção. Todos os 302 warnings coletados são de dependências externas.

---

## 2. Tests Executed

### Gate Primário (E2)
**Comando:** `python -m pytest tests/test_rag_orchestrator.py tests/test_rag_policy.py tests/test_rag_trace_logger.py tests/test_tts_router.py tests/test_audio_reader_service.py tests/test_database.py tests/test_concurrency.py -v --tb=short`

**Arquivos:**
- `tests/test_rag_orchestrator.py`
- `tests/test_rag_policy.py`
- `tests/test_rag_trace_logger.py`
- `tests/test_tts_router.py`
- `tests/test_audio_reader_service.py`
- `tests/test_database.py`
- `tests/test_concurrency.py`

### Suíte Completa (E3)
**Comando:** `python -m pytest tests/ -v -W all --tb=short`

---

## 3. Test Results

### Gate Primário (E2)
| Métrica | Valor |
|---|---|
| Passed | 111 |
| Failed | 0 |
| Skipped | 0 |
| Tempo | 8.54s |

### Suíte Completa (E3 / E9)
| Métrica | Valor | Baseline 13B | Delta |
|---|---|---|---|
| Passed | 345 | 345 | 0 (sem regressão) |
| Failed | 0 | 0 | 0 |
| Skipped | 3 | 3 | 0 |
| Warnings | 302 | N/A* | — |
| Tempo | 175.89s | N/A | — |

> *A Fase 13B não registrou contagem explícita de warnings com `-W all`. A contagem de 302 é a primeira medição de baseline de warnings.

**Skips (3):** Todos em `test_audio_reader_integration.py`, condicionados à ausência dos módulos `kokoro` e `piper` no venv atual:
- `test_piper_model_cache_reused`
- `test_provider_format_metadata`
- `test_kokoro_streaming_generator`

---

## 4. Warnings Triaged

### 4.1 Warnings Internos (código em `src/` ou `tests/`)

**Nenhum warning interno detectado.**

Nenhum arquivo em `src/` ou `tests/` emitiu `DeprecationWarning`, `ResourceWarning`, `SyntaxWarning` ou qualquer outro tipo de warning. O código do projeto está limpo de warnings.

### 4.2 Warnings Externos (dependências)

| ID | Pacote | Warning | Ocorrências | Classificação | Ação |
|---|---|---|---|---|---|
| **W-01** | `chromadb` (via `pydantic`) | `PydanticDeprecatedSince211: Accessing 'model_fields' on instance deprecated` | 301 | **Suprimível** | Será emitido pelo chromadb enquanto `chromadb < 1.0` usar Pydantic V2.11+ internamente. Sem impacto funcional. Pode ser suprimido com filtro em `pyproject.toml`. |
| **W-02** | `opentelemetry` | `DeprecationWarning: SelectableGroups dict interface deprecated` | 1 | **Informativo** | Emitido pelo pipeline de telemetria interno do chromadb. Sem impacto funcional. Não requer ação. |

#### Proposta de Supressão (W-01)

O warning W-01 é extremamente ruidoso (301 ocorrências, de uma única linha em `chromadb/types.py`). Proposta de filtro específico em `pyproject.toml`:

```toml
[tool.pytest.ini_options]
filterwarnings = [
    # Externo: chromadb usa Pydantic V2 internamente — deprecation em model_fields
    # Não mascara warnings internos pois o filtro é restrito ao módulo chromadb.types
    "ignore:Accessing the 'model_fields' attribute on the instance is deprecated:DeprecationWarning:chromadb.types",
    # Externo: opentelemetry SelectableGroups via chromadb
    "ignore:SelectableGroups dict interface is deprecated:DeprecationWarning:opentelemetry",
]
```

> [!IMPORTANT]
> Os filtros acima são **específicos por módulo** (`chromadb.types`, `opentelemetry`). Eles **não podem mascarar** warnings emitidos por código em `src/` ou `tests/`, pois o campo de módulo restringe o match exclusivamente aos pacotes externos listados.

**Status:** Proposta documentada. **Não aplicada** — aguarda aprovação do usuário conforme refinamento solicitado.

---

## 5. Baseline Operacional

### 5.1 Fatos Observados

Cada fato abaixo foi coletado por comando executado diretamente no ambiente do usuário.

| Fato | Método | Output Observado |
|---|---|---|
| Python | `sys.version` | `3.11.9 (tags/v3.11.9:de54cf5, Apr  2 2024, 10:12:12) [MSC v.1938 64 bit (AMD64)]` |
| OS | `platform.platform()` | `Windows-10-10.0.26200-SP0` |
| Arquitetura | `platform.machine()` | `AMD64` |
| RAM Total | `GlobalMemoryStatusEx` | **31.9 GB** |
| RAM Disponível | `GlobalMemoryStatusEx` | **14.17 GB** |
| PyTorch importável | `import torch` | **False** — `OSError: [WinError 193] cusparse64_11.dll não é um aplicativo Win32 válido` |
| CUDA disponível | N/A (torch não importa) | **Indeterminado** — bloqueado por DLL incompatível |
| `HAS_TORCH` (HardwareCapabilityService) | `from src.core.hardware_capability_service import HAS_TORCH` | **False** |
| Tier Recomendado | `HardwareCapabilityService.get_recommended_tier()` | **Tier B** (`gemma4:e4b`) |
| Kokoro cache materializado | Verificação de filesystem | **True** — snapshot `f3ff3571791e39611d31c381e3a41a3af07b4987` com `config.json`, `kokoro-v1_0.pth`, `voices/` |
| Kokoro importável | `import kokoro` | **False** — `No module named 'kokoro'` |
| Ollama status | `http://localhost:11434/api/tags` | **RUNNING** |
| Modelos Ollama | API response | `mistral`, `gemma4:12b`, `qwen3.6:27b`, `gemma4:e4b`, `gemma3:4b`, `qwen2.5-coder:14b`, `llama3`, `gemma4:26b`, `qwen2.5:3b`, `nomic-embed-text:v1.5`, `phi3` |
| Testes totais | `pytest --co` | 348 coletados |
| Resultado testes | `pytest tests/` | 345 passed, 3 skipped, 0 failed |
| Warnings | `pytest -W all` | 302 (todos externos) |
| Provider TTS registration | `auto_register_providers()` | **Falha** — `Qwen3TTSProvider` tenta importar `torch`, que falha com DLL error |

### 5.2 Inferências Derivadas

Cada inferência abaixo é derivada dos fatos da seção 5.1 e marcada explicitamente como inferência.

| Inferência | Fatos Base | Raciocínio |
|---|---|---|
| **O pipeline TTS Kokoro não está funcional neste ambiente** | `kokoro_importable=False`, `torch_importable=False` | Kokoro requer tanto o pacote `kokoro` quanto `torch`. Ambos não estão disponíveis neste venv. O modelo está em cache (pesos baixados), mas o runtime não pode ser instanciado. |
| **O SLO de TTFB de 3s não pode ser medido neste ambiente** | `kokoro_importable=False` | Sem Kokoro funcional, não há como medir TTFB real. O SLO permanece como meta de design, verificável apenas quando o ambiente TTS estiver operacional. |
| **O fallback Kokoro→Piper não será acionado** | `kokoro_importable=False`, nenhum provider TTS registrado com sucesso | Se nenhum provider TTS neural está disponível, o sistema operaria em modo pyttsx3 (Legacy/SAPI5) ou sem TTS. |
| **O RAG está funcional** | `ollama_status=RUNNING`, 345 testes passam, modelos `gemma4:e4b` e `nomic-embed-text:v1.5` presentes | O pipeline completo de RAG (embeddings + chat) está operacional. |
| **A DLL incompatível de torch é provavelmente um mismatch de CUDA toolkit** | `torch_import_error: cusparse64_11.dll`, `HAS_TORCH=False`, venv em path diferente (`H:\PYTHON\assistente-virtual\venv`) | O torch instalado foi compilado para uma versão de CUDA cujas DLLs não estão presentes ou são incompatíveis com o sistema. O venv compartilhado (`assistente-virtual`) pode ter torch de outro projeto com requisitos CUDA diferentes. |
| **O ambiente de testes funciona corretamente apesar do torch DLL error** | 345 testes passam, `HAS_TORCH=False` tratado com graceful degradation | O código do projeto lida corretamente com `HAS_TORCH=False` via try/except no import. Testes que dependem de torch/kokoro são skipped. A degradação graciosa (ADR-005) funciona. |

---

## 6. Diagnóstico GPU / PyTorch / Kokoro / Fallback

### Cadeia de Evidências Completa

| Passo | Comando/Fonte | Output Observado | Conclusão |
|---|---|---|---|
| **1. CUDA disponível?** | `import torch` | ❌ `OSError: cusparse64_11.dll` — torch não importa | **Indeterminado** — torch não carrega, CUDA não pode ser verificada |
| **2. GPU identificada?** | N/A (torch falha) | N/A | **Não verificável** neste ambiente |
| **3. Arquiteturas suportadas?** | N/A (torch falha) | N/A | **Não verificável** neste ambiente |
| **4. Kokoro CUDA compat?** | N/A (torch falha) | N/A | **Não verificável** — KokoroProvider não pode ser instanciado |
| **5. Kokoro cache local?** | Verificação de filesystem | ✅ `True` — snapshot completo com `config.json`, `kokoro-v1_0.pth`, `voices/` | **Cache materializado** — modelo baixado e íntegro |
| **6. Kokoro importável?** | `import kokoro` | ❌ `No module named 'kokoro'` | **Pacote não instalado** neste venv |
| **7. TTFB medido?** | N/A (kokoro indisponível) | N/A | **Não mensurável** neste ambiente |
| **8. Fallback provider?** | `auto_register_providers()` | ❌ Falha na registration de Qwen3TTS (torch DLL) — cascata de falha interrompe o registro | **Nenhum provider neural registrado** |
| **9. HardwareCapabilityService** | `get_recommended_tier()` | `Tier B` / `gemma4:e4b` | HAS_TORCH=False → fallback para detecção de RAM (31.9 GB ≥ 8 GB → Tier B) |
| **10. Ollama** | HTTP GET `/api/tags` | ✅ Running — 11 modelos incluindo `gemma4:e4b`, `gemma4:12b`, `nomic-embed-text:v1.5` | **Ollama operacional** com modelos para RAG |

### Diagnóstico Consolidado

O ambiente atual apresenta **torch com DLL incompatível** (`cusparse64_11.dll` do CUDA toolkit não carrega), o que impede a instanciação de qualquer provider TTS neural (Kokoro, Qwen3-TTS). O pacote `kokoro` também não está instalado neste venv. Contudo:

1. O **cache de modelo Kokoro** está materializado (pesos baixados corretamente)
2. O **Ollama** está operacional com todos os modelos necessários para RAG
3. O **código do projeto** lida corretamente com a indisponibilidade via graceful degradation (`HAS_TORCH=False`)
4. Os **testes** passam corretamente, com skips apropriados para backends indisponíveis

---

## 7. Validação de Runbooks

### 7.1 Cenários Seguros (Executados)

| Cenário | Runbook | Resultado |
|---|---|---|
| Executar testes gate primário | `testing_and_validation.md` §2-3 | ✅ 111 passed, 0 failed |
| Executar suíte completa | `testing_and_validation.md` §3 | ✅ 345 passed, 3 skipped, 0 failed |
| Verificar que os arquivos de teste listados existem | `testing_and_validation.md` §1 | ✅ Todos os 36 arquivos de teste presentes |

### 7.2 Cenários Destrutivos (Verificados Documentalmente)

| Cenário | Runbook | Verificação |
|---|---|---|
| Recuperação de SQLite corrompido | `recovery_and_rollback.md` §1 | ✅ Comandos sintaticamente corretos, `data/library.db` existe. **Não executado** — requer cópia de segurança do DB. |
| Limpeza do ChromaDB | `recovery_and_rollback.md` §2 | ✅ Path `data/chroma_db/` verificado como existente. `DocumentIndexerService.reconcile_all_indexes()` é método documentado. **Não executado** — requer backup prévio. |
| Limpeza de traces | `recovery_and_rollback.md` §3 | ✅ Path `data/traces/` existe. Comando de retenção `src.tools.trace_retention` é módulo existente e testado (`test_trace_retention.py` passa). **Não executado** — traces são dados do usuário. |
| Rollback de código via Git | `recovery_and_rollback.md` §4 | ✅ Repositório Git ativo. Comandos `git log`, `git reset` são válidos. **Não executado** — ação destrutiva requer aprovação humana. |
| Exclusão/regeneração de config.json | `recovery_and_rollback.md` §4 | ✅ `data/config.json` existe. Comportamento de regeneração é documentado. **Não executado** — requer aprovação humana. |

---

## 8. Architectural Rules Applied

- **Separação GUI/Core (ADR-006):** Verificado por grep em `src/core/` — nenhuma importação de PyQt6 nos módulos core RAG/TTS.
  - Nota: `proactive_reader_service.py`, `translation_service.py`, e `watcher.py` importam PyQt6, mas são serviços de aplicação (não parte de `src/core/rag/` ou `src/core/tts/`). Pré-existente e consistente com fases anteriores.
- **PolicyEngine (ADR-003):** Verificado por `test_rag_policy.py` — 4 testes passam.
- **ToolOutput Contract (ADR-001):** Verificado por `test_rag_orchestrator.py` — testes de `ToolOutput` passam.
- **Tracing Estruturado (ADR-004):** Verificado por `test_rag_trace_logger.py` — 3 testes passam.
- **Failure Strategy (ADR-005):** Verificado por `test_rag_orchestrator.py` — testes de fallback e degradação passam.
- **Governance (`AGENTS.md`, `governance.md`):** Execução sequencial, sem subagentes, sem modificações destrutivas, sem introdução de dependências externas.

---

## 9. ADRs Consulted

| ADR | Título | Motivo |
|---|---|---|
| ADR-001 | Uniform ToolOutput Contract | Verificação de invariante INV-03 |
| ADR-004 | Structured Agent Trace Logger | Verificação de invariante INV-04 |
| ADR-005 | Failure Strategy and Graceful Degradation | Verificação de fallback TTS/RAG e INV-05 |
| ADR-006 | GUI/Core AI Boundary | Verificação de invariante INV-01 |
| ADR-007 | Audio Reader Local TTS | Contexto do pipeline TTS e diagnóstico Kokoro |

---

## 10. Invariants Verified

| Invariante | Verificação | Resultado |
|---|---|---|
| **INV-01: Boundary GUI/Core** | `grep "from PyQt6\|import PyQt6\|from src.gui" src/core/rag/ src/core/tts/` | ✅ Limpo — zero matches nos módulos core RAG/TTS |
| **INV-02: PolicyEngine** | `test_rag_policy.py` — 4 testes | ✅ 4/4 passed |
| **INV-03: ToolOutput Contract** | `test_rag_orchestrator.py` — testes de ToolOutput | ✅ Passed |
| **INV-04: Tracing Estruturado** | `test_rag_trace_logger.py` — 3 testes | ✅ 3/3 passed |
| **INV-05: Graceful Degradation** | `test_rag_orchestrator.py` — cenários de fallback | ✅ Passed |
| **INV-06: SQLite Hardening** | `test_database.py` (13 testes) + `test_concurrency.py` (1 teste) | ✅ 14/14 passed |
| **INV-07: TTS Fallback Chain** | `test_tts_router.py` — 21 testes incluindo fallback, readiness, chunking | ✅ 21/21 passed |

---

## 11. Known Risks or Limitations

| ID | Risco | Impacto | Observação |
|---|---|---|---|
| **R-DLL** | `torch` não importa devido a DLL incompatível (`cusparse64_11.dll`) | TTS neural (Kokoro, Qwen3) e tradução NLLB inoperantes em runtime | Venv compartilhado (`H:\PYTHON\assistente-virtual\venv`) pode ter torch de build CUDA incompatível. O código trata via `HAS_TORCH=False`. Testes passam com skips. |
| **R-KOKORO** | Pacote `kokoro` não instalado neste venv | TTS Kokoro não pode ser instanciado mesmo se torch funcionasse | Cache de modelo está materializado (pesos OK), mas o pacote Python precisa ser instalado. |
| **R-TTS-PROVIDERS** | `auto_register_providers()` falha ao registrar Qwen3TTSProvider | Cascata: torch DLL error impede registro de providers que dependem de torch no `__init__` | O router poderia ser melhorado para capturar `OSError` além de `ImportError`/`TTSProviderUnavailable` |
| **R-VENV** | O venv ativo está em path diferente (`H:\PYTHON\assistente-virtual\venv`) do projeto (`G:\PROGRAMAS PYTHON\Biblioteca-pessoal`) | Dependências podem não estar alinhadas com o `requirements.txt` do projeto | Recomenda-se validação em venv dedicada ao projeto |

---

## 12. Any Skipped Verification

| Verificação | Motivo | Impacto |
|---|---|---|
| TTFB real do Kokoro | Pacote `kokoro` não instalado e `torch` não importa | SLO de 3s não pode ser medido neste ambiente |
| Provider TTS registration completa | `torch` DLL error causa cascata na registration | Nenhum provider neural foi testado em runtime real |
| Validação em ambiente limpo (clean-env) | Requer destruição/recreação de venv — ação destrutiva | Documentada mas não executada (conforme plano aprovado) |
| Cenários destrutivos dos runbooks | Requerem cópia de segurança ou aprovação humana | Verificados documentalmente (paths existem, comandos são válidos) |
| Medição real de latência RAG com Ollama | Requer query real ao Ollama (não é escopo de teste automatizado) | Baseline de 8.96s da Fase 13B permanece como referência |
