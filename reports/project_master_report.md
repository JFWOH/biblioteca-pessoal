# Relatório Mestre de Auditoria Técnica e Gestão de Desenvolvimento
## Projeto: Biblioteca Pessoal Inteligente
**Data da Auditoria:** Junho de 2026
**Fase Atual Consolidada:** Fase 13A (Otimização do Pipeline de Narração)
**Status do Projeto:** ENGINEERING-DRIVEN / PRODUCTION-READY PARA USO LOCAL

---

## Bloco A: Introdução e Escopo de Produto

Este documento consolida o estado técnico e gerencial do projeto **Biblioteca Pessoal Inteligente**. O produto atua como um leitor digital multi-formato "local-first" turbinado com capacidades de RAG (Retrieval-Augmented Generation), anotações não destrutivas, e IA Agentic iterativa com mutações de UI seguras. Toda a execução prioriza autonomia, processamento local (Ollama + modelos locais), sem dependência de serviços em nuvem.

---

## Bloco B: Arquitetura e Decisões Técnicas (ADRs)

A arquitetura respeita estritamente o princípio **Event-Driven UI + Background Workers + Core AI decoupling**, garantido pelos ADRs (Architecture Decision Records) ativos:

- **ADR-003 (Policy Engine):** Nenhuma alteração de UI gerada pelo modelo pode ser renderizada sem validação prévia de segurança.
- **ADR-004 (Structured Trace Logger):** Auditoria operacional persistida localmente em JSONL, sem vazamento de PII desnecessário.
- **ADR-006 (GUI / Core AI Boundary):** Separação drástica entre Qt e Core. A lógica cognitiva (`src/core/`) nunca deve instanciar artefatos `PyQt6`. Toda mutação transita via signals/slots (`QThread`).
- **Arquitetura de Banco (SQLite Hardening):** Implementação de *single-writer lock* e isolamento `threading.local()` no módulo `database.py` para prevenção de falhas de corrupção.

---

## Bloco C: Pipeline de IA e Agentic RAG

O caminho canônico do RAG foi 100% centralizado no `src/core/rag/orchestrator.py`. A interface RAG atua seguindo a lógica:
1. Recebimento da query (QThread RAGWorker).
2. Construção dinâmica de contexto (ChromaDB + SQLite FTS5 + Histórico de Sessão + Texto Atual).
3. Chamada ao Ollama (`gemma4:e4b` ou similares).
4. Interpretação de Tool Calls (`vector_search`, `highlight_book_text`, etc).
5. Passagem obrigatória pelo **PolicyEngine** caso a tool solicite mutação visual (ex. Highlights efêmeros).
6. Stream de respostas e logs no `TraceLogger`.

---

## Bloco D: Módulo TTS e Áudio Contínuo (Phase 13A)

Uma das maiores vitórias de engenharia recentes foi a refatoração profunda do sistema de leitura expressiva em voz:
- **TTS Router Multitier:** `kokoro_provider.py` atuando como Tier B (Primary High-Quality offline) e `piper_provider.py` atuando como Tier C (Fallback de latência estrita).
- **Vetorização NumPy:** O gargalo crítico de CPU que resultava em atrasos insustentáveis de float32 para PCM foi substituído por operações nativas vetorizadas com NumPy (`audio_data * 32767`).
- **Lifecycle do Modelo:** O TTSRouter não é mais destruído e instanciado a cada interação; seu ciclo de vida foi atrelado ao `AudioReaderService` (Single-instance em memória), com *warmup assíncrono* em thread daemon.
- **Stream Segmentado:** O envio do generator e do áudio agora é gerenciado ativamente via chunking (`TextChunker`) para reduzir latência de TTFB.

---

## Bloco E: Governança, Concorrência e Isolamento (UI vs Core)

A estabilidade técnica sob carga de execução LLM e TTS repousa sobre as seguintes decisões de concorrência:
- `QWebEngineView` e `PyMuPDF` isolados em renderizações passivas. O motor Core só consulta o backend por posições em página, minimizando o locking.
- Bloqueio rígido no `library.db` (SQLite3) usando `threading.Lock()` para operações escritas, evitando que o `AudioWorker`, o `RAGWorker` e a `MainWindow` entrem em *deadlocks*.

---

## Bloco F: Performance, Observabilidade e Tracing

A capacidade de auditar o projeto foi profissionalizada:
- Geração de artefatos `<timestamp>_trace.jsonl` em `data/traces/`.
- Uso do `rag_eval_harness.py` e do `trace_inspector.py` permitindo que a equipe audite loops redundantes, uso excessivo de fallbacks ou falhas na extração de parâmetros das ferramentas.
- Prefix Caching nativo e envio minimalista de assinaturas de `_TOOLS_DEF` para diminuir sobrecarga nos LLMs locais limitados.

---

## Bloco G: Segurança de UI e Mutações

O assistente RAG pode atuar no ambiente do usuário sem risco de apagar livros ou corromper anotações:
- As anotações/highlights ("mutações visuais efêmeras e persistidas") criadas via IA (`create_ai_bookmark`, `highlight_book_text`) são validadas semanticamente.
- Nenhuma alteração é gravada irreversivelmente no arquivo PDF/EPUB de origem. Elas residem no banco de metadados SQLite.

---

## Bloco H: Infraestrutura de Testes e Maturidade

- Suíte de Testes Contínua cobrindo +340 cenários vitais.
- A cobertura é pesada nos núcleos críticos: `test_rag_orchestrator.py`, `test_rag_policy.py`, `test_rag_trace_logger.py` e agora os testes de TTS em `test_audio_reader_service.py`.
- Os testes garantem regressão zero durante as refatorações pesadas (ex. Fase 13A para NumPy arrays).

---

## Bloco I: Mapa de Riscos (Risk Register)

| ID Risco | Área | Descrição | Nível | Mitigação Atual |
|---|---|---|---|---|
| RSK-01 | **Performance Local** | Dependência de Ollama com modelos grandes limitando responsividade na GPU/CPU unificada | Alto | Tool Def compactado, Prefix caching, Roteamento adaptativo (Kokoro -> Piper). |
| RSK-02 | **Estabilidade PyQt** | Event loops da thread gráfica congelando durante chamadas longas do TTS | Médio | Delegação total de `tts_backend.synthesize` para QThreads; Signals thread-safe. |
| RSK-03 | **Mudanças da API Ollama**| Modelos atualizados ou daemon do Ollama mudando contratos de `message` e `tools` | Médio | Tratamentos try/except extensos no facade `rag_engine` e failover gracioso. |

---

## Bloco J: Próximos Passos (Roadmap 14 e 15)

O sistema estabilizou os pipelines de Leitura, Estudo e Áudio. As próximas fronteiras são:
- **Fase 14 (Multimodalidade RAG):** Capacidade de o Agente interpretar layouts visuais complexos, fluxogramas, gráficos em PDFs utilizando capacidades Vision dos LLMs.
- **Fase 15 (Sincronização Distribuída):** Prover suporte confiável (possivelmente CRDTs ou Merkle Trees simples) para sync de highlights e leitura entre instâncias independentes da aplicação sem serviço em nuvem.
- **Escalabilidade Experimental:** Aprimorar o chunking e a indexação do banco ChromaDB para aguentar acervos com mais de 500.000 tokens de busca por volume.
