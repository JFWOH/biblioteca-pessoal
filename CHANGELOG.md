# Changelog

Todas as mudanças notáveis no projeto **Biblioteca Pessoal Inteligente** serão documentadas neste arquivo.

O formato é estruturado para humanos, orientado ao impacto e baseado no padrão [Keep a Changelog](https://keepachangelog.com/pt-BR/1.0.0/).

## [Unreleased]
- **Recursos Futuros**: Multimodalidade.

## [Fase 12] - Ferramentas de Estudo (Flashcards) + Integração com Anki
### Added
- **`AnkiService` Local**: Serviço core desacoplado para comunicação via HTTP com a API local do **AnkiConnect** (`127.0.0.1:8765`).
- **`AnkiExportDialog`**: Diálogo de UI para revisão de Frente e Verso (Basic Model) do flashcard antes da inserção, incluindo seleção de *Deck*.
- **Ações de Contexto no ReaderView**: Adicionada opção `"🃏 Criar Flashcard"` ao selecionar trechos de texto em EPUB e PDF.
- **Ações de Contexto no Assistente (RAG / Proativo)**: Um novo botão no `ProactiveFooterWidget` e na resposta do `RAGPanel` permite capturar o texto e as observações diretas da IA para geração instantânea de flashcards.
- **Worker Assíncrono (`AnkiWorker`)**: Proteção do *Event Loop* garantindo que requisições HTTP para o AnkiConnect ocorram em thread separada.
- **Fallback Tolerante a Falhas**: Caso o usuário solicite salvar um flashcard mas o Anki Desktop não esteja aberto (ou sem o AnkiConnect), o sistema salva graciosamente em `data/flashcards_fallback.jsonl`, permitindo exportação futura sem perder a nota de estudo.

## [Fase 11] - Agente Proativo de Leitura (MVP)
### Added
- **Painel Proativo (`ProactiveFooterWidget`)**: Adicionado um rodapé dinâmico ao ReaderView para exibir observações automáticas (Contexto, Hipótese ou Observação de Texto) baseadas na página lida, de forma discreta e animada.
- **`ProactiveTriggerEngine`**: Motor heurístico desenvolvido para calcular o momento exato de acionar o agente com base na taxa de leitura (WPM) e na intensidade textual.
- **Worker Assíncrono (`ProactiveWorker`)**: Integrado à API do Ollama sem bloquear a interface de usuário. Inclui parser JSON tolerante a falhas que purifica formatações corrompidas (markdown ou texto residual) e suporte nativo a modelos baseados em raciocínio (Reasoning Models) ajustando o `num_predict` para 4096.
- **Hardware Capability Service**: Sistema de fallback que seleciona inteligentemente o modelo adequado ("gemma4:e4b" para TIER_4, fallback em memória para sistemas sem suporte pesado), evitando gargalos térmicos e de VRAM.
- **Botão de Alternância ("💡 Proativo: ON/OFF")**: Injetado na toolbar de leitura, garantindo que a geração em background seja sempre opcional e sob controle do leitor.
- **Expansão do Catálogo de Modelos (UI)**: Adicionado suporte nativo ao `gemma4:12b` (Gemma 4 12B) direto no painel de seleção RAG, classificado como "🔥 Poderoso".

### Fixed
- **Bug do Layout Maximizado**: Solucionado um erro no `ReaderView` que empurrava a barra de progresso verde para fora da tela ao maximizar a janela. Um `QSizePolicy.Ignored` foi atrelado ao WebEngineView para respeitar os limites de tela rigorosamente.
- **Crash de Parseamento (Ollama)**: Removida a trava rígida de formato (`format: json`) da API do Ollama para permitir o fluxo natural de modelos R1-like ou com output enriquecido, extraindo o JSON pelo worker seguro.

### Note
- **Requisitos**: Modelos Proativos necessitam das flags ideais na resposta. Limite agressivo de tokens durante o pensamento do modelo foi remediado pelo novo limite de output.
- **Configuração Estrita de Limites**: Parâmetros `num_predict` e `num_ctx` injetados dinamicamente no payload de chamadas da Ollama API, evitando interrupções curtas.
- **Continuação Transparente e Segura**: Identificação proativa de `done_reason="length"` para forçar a continuação do output do assistente sem reiniciar as cadeias lógicas (limitado para prevenir looping).
### Fixed
- Interrupções textuais no meio de mensagens mais densas ou em explicações embutidas nos bookmarks gerados pela inteligência.
- Truncagem de output visual nas respostas combinadas a chamadas de ferramentas.

## [Fase 9] - Reader UI Refresh & Audio TTS
### Added
- **Design System Emerald**: Refatoração completa da paleta de cores para o tom "Dark-First Emerald" nos temas Dark, Light e Sépia (remoção das antigas heranças roxas).
- **Leitor de Áudio (TTS)**: Integração de um leitor de texto nativo (`pyttsx3`) rodando em background (`QThread`) sem bloquear a UI. Inclui sanitização avançada de texto para ignorar quebras de linha e referências bibliográficas do PDF.
- **Barra de Pesquisa (Overlay)**: Tema escuro hardcoded removido. Agora a barra respeita dinamicamente o tema ativo da interface.
- **Tipografia**: Unificação de fontes para que todos os temas (incluindo o Sépia) usem a fonte padronizada (Segoe UI / Inter).
### Changed
- **Sidebars Refinadas**: Painéis de TOC, RAG e Anotações modernizados com bordas sutis, gradientes de destaque para elementos selecionados e alinhamento responsivo.
- **Navegação de Página**: Comportamento de navegação ajustado para sempre resetar o viewport para o topo ao trocar de página, garantindo consistência na leitura contínua (EPUB e PDF).

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
