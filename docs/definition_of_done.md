# Definition of Done (DoD)
## Critérios de Qualidade e Prontidão de Entrega

Este documento estabelece as diretrizes mínimas obrigatórias que qualquer alteração de código ou funcionalidade deve cumprir antes de ser considerada concluída ("Done") e integrada ao repositório principal do projeto **Biblioteca Pessoal Inteligente**.

---

## 1. Código e Padrões de Implementação
- **Conformidade Arquitetural (ADR-006):** Separação estrita entre a interface de usuário (PyQt6 em `src/gui/`) e a lógica cognitiva do RAG/TTS (Core em `src/core/`). O diretório `src/core/` não deve importar `PyQt6` ou qualquer classe dependente de UI.
- **Formatação e Linting:** Código limpo, legível e formatado via Ruff de acordo com as configurações do `pyproject.toml` (comprimento de linha máximo de 100 caracteres).
- **Sem Comentários/Código Morto:** Nenhum código comentado ou trecho não utilizado (placeholders temporários, TODOs órfãos) deve permanecer no código final.
- **Tratamento de Exceções:** Erros de I/O, falhas de rede (Ollama offline, ChromaDB indisponível, etc.) devem ser tratados com estratégias de fallback graciosas (ADR-005) e devidamente logados, sem silenciar exceções de forma oculta.

## 2. Testes e Cobertura
- **Testes Unitários e de Integração:** Toda nova funcionalidade deve possuir cobertura de testes adequada, focando principalmente no comportamento do pipeline RAG (`orchestrator.py`), regras do `policy_engine.py`, persistência no SQLite e ciclo de vida do `tts_router.py`.
- **Suíte de Testes como Gate:**
  1. Executar **testes focados** na área impactada em primeiro lugar.
  2. Executar a **suíte completa** (`python -m pytest tests/`) e garantir 100% de aprovação (ou registrar e documentar o motivo exato caso o ambiente de release impeça a execução completa).
- **Concorrência Segura:** Testes envolvendo concorrência (múltiplas threads lendo/escrevendo dados de leitura ou anotações) devem ser validados exaustivamente para assegurar que não introduzem regressões ou travamentos no *single-writer lock* do SQLite.

## 3. Segurança e Governança de UI
- **Zero Secrets:** Credenciais, tokens de API ou caminhos absolutos de sistema local não devem ser gravados de forma hardcoded.
- **Policy Engine (ADR-003):** Todas as mutações de interface sugeridas por agentes de IA (como destaques em blocos de texto ou inserção de marcadores) devem passar obrigatoriamente pelo `PolicyEngine` para validação de segurança antes de transitar à GUI.
- **Higienização de Inputs:** Inputs de texto extraídos de arquivos externos (PDF, EPUB) ou web search devem ser higienizados e tratados como não confiáveis antes do envio ao LLM ou TTS.

## 4. Observabilidade e Tracing (ADR-004)
- **Log de Eventos Estruturados:** Qualquer fluxo agentic crítico do RAG deve gerar traces estruturados append-only no formato JSONL sob o diretório `data/traces/`.
- **Sanitização de Payloads:** Payloads muito extensos ou que contenham dados privados devem ser devidamente truncados ou higienizados pelo `TraceLogger` para otimizar desempenho de I/O e privacidade.
- **Trace Inspector & Harness:** As novas sessões geradas devem passar na validação estrutural do harness de avaliação (`rag_eval_harness.py`).

## 5. Documentação Operacional
- **Roadmap e CHANGELOG:** O `project_report.md` e o `CHANGELOG.md` devem ser mantidos atualizados com o progresso das entregas.
- **Runbooks e Guias:** Qualquer nova ferramenta, script auxiliar ou backend de IA adicionado deve ter seu respectivo runbook de validação rápida e instruções de recuperação documentados.

## 6. Rollback e Recuperação
- **Mudanças Reversíveis:** Toda alteração significativa deve conter um plano de rollback documentado.
- **Segurança de Dados:** O estado do banco de dados relacional e vetorial deve permanecer consistente; migrations (se houverem) devem possuir scripts de downgrade testados.
