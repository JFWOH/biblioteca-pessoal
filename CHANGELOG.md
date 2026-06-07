# Changelog

Todas as mudanças notáveis no projeto **Biblioteca Pessoal Inteligente** serão documentadas neste arquivo.

O formato é estruturado para humanos, orientado ao impacto e baseado no padrão [Keep a Changelog](https://keepachangelog.com/pt-BR/1.0.0/).

## [Unreleased]
- **Integração Visual de OCR**: Uso do cache OCR derivado nativamente no `pdf_reader.py` para habilitar highlight e seleção de texto visual em documentos escaneados.
- **Reader UI Refresh**: Redesign visual profundo "Dark-First" com Glassmorphism (atualmente prototipado em HTML, aguardando implementação nativa PyQt6/QSS via backlog P2-005).
- **Recursos Futuros**: Multimodalidade para diagramas e integração com Anki (Flashcards).

## [Fase 8] - Tradução Offline (MVP)
### Added
- Suporte inicial a tradução de trechos selecionados usando modelo `facebook/nllb-200-distilled-600M` (limite: 2000 caracteres por chamada).
- `TranslationService` desacoplado rodando em worker assíncrono (`QThread`) isolado da thread principal da GUI.
- Novas dependências no setup e `requirements.txt`: `transformers`, `torch`, `sentencepiece`.
- Integração pontual via menu de contexto ("🌐 Traduzir Seleção") do leitor `ReaderView` em PDFs e EPUBs.
- Fallback controlado (Graceful Degradation): se o modelo não estiver em cache e não houver internet, a UI exibe erro claro na statusbar sem travar o app.

### Notes
- **Ressalva de operação offline**: exige conexão com a internet exclusivamente na **primeira execução** para download do modelo (~2.5GB) para a cache local do HuggingFace. Execuções posteriores são 100% offline.
- **Limites operacionais**: texto truncado a 2000 caracteres; inferência em CPU leva ~5-15s por bloco; em GPU (~1.2GB VRAM), ~1-3s.
- **Escopo restrito**: MVP limitado a trechos selecionados. Tradução de documento inteiro, tradução em lote e integração com o `Orchestrator` estão fora de escopo desta fase.

## [Fase 7] - Cache e Persistência de OCR (Implementação Parcial)
### Notes
- *Status*: Implementação parcial comprovada no backend. A infraestrutura de armazenamento e reaproveitamento de OCR foi finalizada para a ingestão vetorial (RAG), mas ainda aguarda a consolidação na interface do usuário (Leitor nativo).

### Added
- **Cache OCR Derivado**: Suporte introduzido no SQLite (`save_ocr_page`, `get_ocr_page`) e no `DocumentIndexerService` para armazenar a extração textual de documentos escaneados, eliminando redundâncias computacionais no Tesseract.
- **Testes de Integração**: Suíte `test_pdf_reader_ocr_integration.py` validando o comportamento de fallback e hit no cache OCR durante a geração de embeddings do RAG.

## [Fase 6.1] - SQLite Hardening e Segurança Concorrente
### Fixed
- **Condições de Corrida no Banco**: Resolução de `DatabaseError: malformed` (decorrente de deadlocks de escrita concorrente) via adoção de um bloqueio global `single-writer` (`threading.Lock()`).
- **Isolamento de Conexão**: Gerenciamento estrito usando `threading.local()`, com garantia de persistência e operação assíncrona segura no modo WAL (Write-Ahead Logging).
- Adicionada bateria massiva de testes para validar a resiliência em cenários de alta concorrência.

## [Fase 6] - Integridade de Indexação e Refatoração de Ingestão
### Changed
- **Desacoplamento de Indexação**: Migração total do pipeline de ingestão pesada, geração de chunks e embeddings do `rag_engine.py` para um novo e dedicado `DocumentIndexerService`.
- O `rag_engine.py` foi simplificado e agora atua apenas como facade para as rotinas de busca semântica.

### Added
- **Controle de Estado de Indexação**: Introdução da tabela `indexing_state` no SQLite, rastreando de forma segura e atômica os status `pending`, `ok` e `failed`.
- Utilitário dedicado (`index_reconcile`) para verificação e reparo de estados de indexação ambíguos.

## [Fase 5] - OCR Local para PDFs Escaneados
### Added
- **OCR Service Nativo**: Integração do pipeline PyMuPDF e `pytesseract` via `ocr_service.py`, adicionando heurísticas automáticas (`is_scanned_pdf`) para acionar fallback de leitura via imagem quando o PDF original contém pouco ou nenhum texto literal.

## [Fase 4] - Qualidade Semântica e Evolução do Estado do Agente
### Added
- **Evolução do AgentState (ADR-002)**: Injeção de metadados semânticos avançados (ex.: `sources_used`, `repeated_result_count`, `web_seen`, `books_consulted`) diretamente no payload dos eventos de finalização de consulta.
- Expansão do **Evaluation Harness** para classificar traces de acordo com seu comportamento semântico e operacional automático (ex.: `healthy`, `redundant`, `fallback_heavy`, `policy_inconsistent`, `error_controlled`).
- O Trace Inspector CLI (`trace_inspector.py`) agora extrai e apresenta as novas métricas de qualidade aos operadores de teste (repetições detectadas, fontes consultadas e blocos de política).

### Fixed
- **Correção Crítica no Ambiente de Testes**: Identificada e corrigida uma regressão severa no componente `tests/test_opds_server.py`. O teste acessava indevidamente a conexão de banco de dados real do usuário local, o que resultava na exclusão acidental em cascata do acervo produtivo real durante o teardown das fixtures. 
- Adicionada segurança rigorosa de isolamento para os testes: o banco agora opera sobre um ambiente temporário hospedado no `tmp_path`, garantindo que os dados em disco originais estejam protegidos e imunes a falhas de chave estrangeira.

### Changed
- Atualização substancial da documentação arquitetural no repositório (`project_report.md`) para refletir e consolidar as integrações geradas durantes as fases 3 e 4.

## [Fase 3] - Operabilidade e Qualidade do RAG
### Added
- Implementação de um fluxo de **Housekeeping/Retenção** local dedicado aos arquivos de rastreio em `data/traces/`.
- Adição do **Trace Inspector CLI** (`trace_inspector.py`), uma ferramenta limpa de console para listar resumos de sessão ou inspecionar cronologicamente os logs estruturados via `session_id`.
- Início da suíte de integridade estrutural com o `rag_eval_harness.py`, possibilitando analisar e acusar anomalias ou traços interrompidos.

## [Fase 2] - Structured Agent Trace Logger
### Added
- Implementação integral do **Structured Agent Trace Logger (ADR-004)**.
- O pipeline de inferência agora persiste sessões e execuções 100% localmente no sistema de arquivos, em formato de linha única (`.jsonl`).
- Eventos centrais como `query_started`, invocação de ferramentas (tool calls), interrupções avaliadas via `policy_decision`, fallback ativado e finalizações estão estritamente rastreados.

### Changed
- O mecanismo de logging implementa contingências seguras (fail-safe). Erros durante o parseamento ou a gravação de traços não escalam para o cliente visual nem travam a consulta da IA principal.

## [Fase 1] - Consolidação do Caminho Canônico do RAG
### Changed
- **Centralização Canônica**: Remoção da fragmentação e duplicidade de fluxo no motor IA. O arquivo `src/core/rag/orchestrator.py` estabeleceu-se como a única fundação autoritativa do loop Agentic RAG.
- O módulo legado `src/core/rag_engine.py` foi simplificado e refatorado em um _facade_ transparente voltado a manter a compatibilidade externa com os módulos adjacentes.
- Desacoplamento aprimorado do despachante `RAGWorker`.
- Endurecimento operacional das políticas: O **Policy Engine (ADR-003)** está enraizado diretamente no motor, bloqueando ações não confiáveis antes mesmo de elas colidirem contra os limites visuais (GUI vs Core, conforme o ADR-006).
