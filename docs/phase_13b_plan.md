# Fase 13B — Plano de Implementação (Aprovado)
## Core Hardening & Private Release Readiness

---

## 1. Resumo Executivo
A Fase 13B visa consolidar o núcleo do projeto **Biblioteca Pessoal Inteligente** como uma base robusta, mensurável e consistente para distribuição privada local. Não serão criadas novas grandes funcionalidades. Em vez disso, o foco está em formalizar o Definition of Done (DoD), identificar e organizar a suíte mínima de testes, criar a infraestrutura de medição de latência e estabilidade (RAG e TTS) priorizando scripts/traces externos e minimizando alterações em `src`, elaborar o checklist de release privado local, consolidar a matriz de compatibilidade e otimizar a documentação operacional e runbooks de recuperação.

## 2. Objetivo
Preparar o sistema para distribuição controlada local (private release) com alta confiança de integridade, provendo ferramentas para diagnóstico de regressão, monitoramento de performance e facilidade de recovery local.

## 3. Escopo
- **A) Definition of Done:** Criação de `docs/definition_of_done.md`.
- **B) Suíte Mínima Obrigatória:** Descoberta, mapeamento e categorização dos testes existentes em `docs/runbooks/testing_and_validation.md`.
- **C) Métricas de Latência e Estabilidade:** Coleta de dados e consolidação de medições de latência de RAG, rounds médios, fallback rate, TTFB do TTS, e latência total de síntese/streaming. A prioridade absoluta é extrair essas métricas por traces existentes, scripts externos ou benchmarks locais executados fora do diretório `src/`. Modificações diretas no código de `src/` devem ser evitadas ao máximo e executadas apenas se inevitáveis e com mudanças mínimas.
- **D) Checklist de Release Privado Local:** Criação de `docs/private_release_checklist.md`.
- **E) Matriz Mínima de Compatibilidade:** Criação de `docs/compatibility_matrix.md`.
- **F) Hardening de Documentação Operacional:** Criação de runbooks de validação e recuperação de falhas em `docs/runbooks/recovery_and_rollback.md` e `docs/runbooks/testing_and_validation.md`.
- **G) Relatório de Execução e Backlog Residual:** Criação de `reports/phase_13b_execution_report.md` e `reports/phase_13b_risk_register.md`.

## 4. Fora de Escopo
- Implementação de RAG Vision / Multimodal (Fase 14).
- Sincronização multi-dispositivo distribuída (Fase 15).
- Redesign visual amplo ou alteração de stack (ex. migração para outro framework GUI).
- Telemetria externa, serviços em nuvem ou dependências de rede não solicitadas.

## 5. Diagnóstico Inicial da Fase
O projeto conta com uma base robusta com mais de 340 testes unitários e de integração. O SQLite foi endurecido com single-writer locks, e o pipeline de TTS foi otimizado (Fase 13A) via vetorização NumPy. No entanto, faltam formalizações operacionais (como fazer rollback, como auditar a latência real de RAG/TTS fora dos logs gerais, como empacotar e validar uma release local) que permitam um empacotamento privado seguro.

## 6. Governança Aplicável (Etapa 0)
- **Leitura Mandatória:**
  - `AGENTS.md` (Contrato de execução e governança)
  - `.agents/rules/governance.md` (Regras de governança do workspace)
  - `.agents/adr/README.md` (Índice de Architectural Decision Records)
- **ADRs que precisam ser consultados antes de tocar qualquer subsistema:**
  - **ADR-001 (Uniform ToolOutput Contract):** Caso alguma ferramenta agentic seja modificada.
  - **ADR-003 (Policy Engine):** Caso toque em UI mutations ou permissões.
  - **ADR-004 (Structured Agent Trace Logger):** Caso altere o formato ou leitura de traces.
  - **ADR-005 (Failure Strategy and Graceful Degradation):** Para lidar com falhas graciosas em RAG/TTS.
  - **ADR-006 (GUI/Core AI Boundary):** Para validar o desacoplamento absoluto do PyQt6 em relação ao core.
  - **ADR-007 (Audio Reader Local TTS):** Estratégia de síntese de áudio.
- **Workflow RAG-Architecture-Governance:** Caso o trabalho toque em `src/core/rag/`, `tools/`, `policy`, `tracing`, `failure handling` ou no boundary `GUI/RAG`, o fluxo estruturado da skill `rag-architecture-governance` será aplicado explicitamente.

## 7. Invariantes que não podem sofrer Regressão
Durante todas as etapas de execução da Fase 13B, os seguintes invariantes arquiteturais devem ser mantidos sem qualquer regressão:
- **Boundary GUI/Core:** `src/core/` não deve importar PyQt6 ou módulos GUI sob qualquer circunstância.
- **PolicyEngine:** Toda e qualquer mutação de UI proposta pela IA deve passar obrigatoriamente pela validação do Policy Engine.
- **ToolOutput:** Todas as tools agentic devem manter estrita aderência ao contrato `ToolOutput` (ADR-001) caso sejam alteradas.
- **Tracing Estruturado:** Todos os passos relevantes do loop de agente devem preservar a integridade do formato estruturado JSONL.
- **Graceful Degradation:** Falhas em Ollama, ChromaDB, SQLite ou Web Search devem resultar em fallback seguro ou degradação silenciosa em vez de crash.
- **SQLite Hardening:** Manutenção do single-writer lock e de conexões thread-local isoladas.

## 8. Estratégia de Execução (Reordenada)
A execução será realizada de forma sequencial com a seguinte ordenação:
- **Etapa 0: Governança e ADR Compliance:** Leitura sistemática e alinhamento com os guias e ADRs do projeto.
- **Etapa 1: Discovery de Testes (Coleta):**
  - Mapear e coletar a lista de todos os testes existentes no repositório.
- **Etapa 2: Execução de Testes Focados:**
  - Rodar em primeiro lugar testes específicos e restritos para validar o funcionamento do RAG, do SQLite e do TTS.
- **Etapa 3: Elaboração da Documentação e Metodologia de Métricas:**
  - Escrever os arquivos base (`docs/definition_of_done.md`, `docs/private_release_checklist.md`, `docs/compatibility_matrix.md`).
  - Preparar os scripts e instruções para coleta de dados de latência de RAG e TTS sem mexer no código de `src/` (ou com mudanças mínimas estritamente inevitáveis).
- **Etapa 4: Runbooks Operacionais:**
  - Criar os guias detalhados de validação de testes e recovery local.
- **Etapa 5: Execução da Suíte Completa:**
  - Execução de `python -m pytest tests/` no final (se o ambiente permitir). Em caso de bloqueio ambiental, o mesmo será registrado em detalhes.
- **Etapa 6: Geração de Relatórios e Backlog Residual.**

## 9. Uso de Subagentes
Não serão utilizados subagentes para esta fase. Como as tarefas envolvem auditoria técnica integrada, documentação coerente e análise sequencial de riscos e testes, a execução por um único agente central evita dispersão e garante coesão contextual total.

## 10. Arquivos previstos de alteração/criação
### Novos Arquivos (Documentação e Relatórios)
- `docs/phase_13b_plan.md` [NEW]
- `docs/definition_of_done.md` [NEW]
- `docs/private_release_checklist.md` [NEW]
- `docs/compatibility_matrix.md` [NEW]
- `docs/runbooks/recovery_and_rollback.md` [NEW]
- `docs/runbooks/testing_and_validation.md` [NEW]
- `reports/phase_13b_execution_report.md` [NEW]
- `reports/phase_13b_risk_register.md` [NEW]
- `reports/phase_13b_metrics.md` [NEW]

### Modificações (Apenas se inevitáveis para instrumentação local de métricas)
- Ajustes mínimos e estritamente localizados em `src/core/rag/trace_logger.py` ou `src/core/tts/tts_router.py`. Prioridade total é utilizar análise externa de traces existentes.

## 11. Testes que serão usados como gates (Se presentes no repositório)
- `tests/test_rag_orchestrator.py` (se presente)
- `tests/test_rag_policy.py` (se presente)
- `tests/test_rag_trace_logger.py` (se presente)
- `tests/test_audio_reader_service.py` (se presente)
- `tests/test_tts_router.py` (se presente)
- `tests/test_database.py` (se presente)
- `tests/test_concurrency.py` (se presente)

## 12. Métricas que serão coletadas
- **RAG Latency:** Tempo médio por round de query e tempo total de resposta.
- **Rounds Médios:** Quantidade média de iterações por consulta do agente.
- **Fallback Rate:** Frequência de acionamento de fallbacks estruturais.
- **TTS TTFB (Time to First Byte):** Tempo entre a solicitação e o início do fluxo de áudio.
- **Total Synthesis Latency:** Tempo de síntese por chunk de texto.
- **Startup Times:** Tempo de carregamento do app e do warmup do TTS.

## 13. Riscos Identificados
- **RIS-01: Divergência entre ambientes locais:** Diferenças de performance de CPU/GPU rodando Ollama/Kokoro podem distorcer as métricas brutas.
  *Mitigação:* Documentar as especificações de hardware onde as métricas foram aferidas e focar na infraestrutura de medição replicável pelo usuário.
- **RIS-02: Bloqueio do banco de dados durante testes concorrentes:** Concorrência artificial nos testes pode causar timeouts.
  *Mitigação:* Garantir uso estrito do backend SQLite com single-writer lock ativo em todos os testes.

## 14. Critérios de Aceite
- Todos os 9 documentos de documentação, runbooks e relatórios criados sob as pastas correspondentes.
- Execução completa e bem-sucedida de `python -m pytest tests/` no ambiente local (se o ambiente permitir).
- Caso o ambiente impeça a execução completa, registrar o bloqueador exato e não declarar sucesso total da suíte completa de testes.
- Ausência total de violações ou regressões nos invariantes de segurança e arquitetura (Boundary, PolicyEngine, ToolOutput, Tracing, SQLite hardening).

## 15. Plano de Rollback
Como a Fase 13B é focada em endurecimento técnico e documentação, o risco para o código de produção é mínimo.
- Caso qualquer modificação em `src/` introduza regressões nos testes, os arquivos modificados serão revertidos para a última revisão do git (`git checkout -- <file>`).
- Validação do rollback através da execução imediata do comando `python -m pytest tests/`.

## 16. Perguntas Operacionais em Aberto
- **A1: Configurações de Path de Voz do Kokoro/Piper:** Onde e como as vozes locais estão configuradas no ambiente do usuário (por exemplo, pasta de cache de modelos Hugging Face ou caminhos estáticos em `config.json`)?
- **A2: Versão e Status do Daemon do Ollama:** O Ollama está rodando localmente na porta padrão (11434) e com quais modelos pré-carregados (ex. gemma)?
- **A3: Restrições de Hardware Locais:** Qual a disponibilidade de GPU (CUDA) ou se a execução está ocorrendo 100% em CPU, impactando diretamente o limiar do SLO de latência de 3 segundos do TTS.

## 17. Ordem de Execução Detalhada
1. **Etapa 0: Alinhamento de Governança e ADRs:** Ler e registrar conformidade com `AGENTS.md`, `.agents/rules/governance.md` e os ADRs relevantes.
2. **Etapa 1: Discovery de Testes:** Listar os arquivos de testes existentes no repositório.
3. **Etapa 2: Execução de Testes Focados:** Rodar testes específicos prioritários de RAG, DB e TTS.
4. **Etapa 3: Definição de DoD:** Escrever `docs/definition_of_done.md`.
5. **Etapa 4: Checklist e Matriz:** Criar `docs/private_release_checklist.md` e `docs/compatibility_matrix.md`.
6. **Etapa 5: Instrumentação Local de Métricas:** Implementar scripts/instruções para extrair latências baseados nos traces JSONL do `TraceLogger` sem mexer no core se possível.
7. **Etapa 6: Runbooks Operacionais:** Escrever os guias em `docs/runbooks/`.
8. **Etapa 7: Execução da Suíte Completa:** Executar `python -m pytest tests/` se o ambiente local permitir, caso contrário relatar impedimentos.
9. **Etapa 8: Relatórios de Execução e Riscos:** Gerar o relatório final estruturado contendo obrigatoriamente os campos:
   - Files changed
   - Tests executed
   - Test results
   - Architectural rules applied
   - ADRs consulted
   - Known risks or limitations
   - Any skipped verification
