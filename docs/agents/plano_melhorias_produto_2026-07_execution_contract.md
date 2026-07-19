# Contrato de Execução — Programa de Melhorias de Produto (jul/2026)

**Objetivo:** implementar TODAS as melhorias da Revisão de Produto & UX de 2026-07-16
(`docs/revisao-produto-ux-2026-07-16.md`, §3 e §5), em execução AUTÔNOMA orquestrada,
com validação integral pelos agentes até a entrega final. **Testes reais com o usuário
acontecem SOMENTE após a entrega completa** (roteiro no §V deste contrato).

**Baseline:** `main` @ `2c79557` (roadmap de 6 fases completo + aprendizado 👍/👎 +
revisão de produto). Suíte: 832 passed; ruff limpo; CI em 2 shards com retry.

---

## I. Modelo de execução (obrigatório)

- **Orquestrador (Fable 5)**: planeja cada onda, congela interfaces entre executores,
  despacha no máx. 10 subagentes por onda (Opus 4.8 para partes difíceis, Sonnet 5
  para mecânicas), sintetiza e VALIDA cada entrega.
- **Por onda**: branch `feature/melhorias-onda-<N>` a partir da `main` → executores com
  whitelists estritas de arquivos (zero colisão) → validação do orquestrador (suíte
  completa `venv\Scripts\python.exe -m pytest tests/ -q` + `ruff check src tests` +
  revisão de diff contra o plano) → PR com corpo descritivo → CI verde → **merge
  automático autorizado por este contrato** → próxima onda.
- **Gate de falha**: se uma onda não ficar verde após 2 tentativas de correção,
  PARAR o programa e reportar ao usuário (não avançar por cima de vermelho).
- **Regras invioláveis**: CLAUDE.md + ADRs (006: core sem PyQt6; 005: degradação
  graciosa; 001: ToolOutput). SEMPRE `venv\Scripts\python.exe`. UI em PT-BR.
  **NUNCA `think=False` no proativo/RAG/explicações** (decisão do usuário de
  2026-06-29 — qualidade > velocidade; `think=False` só onde já é padrão: tarefas
  `fast` como flashcards/título/refino de conceitos).
- **Docs**: cada onda atualiza sua seção neste arquivo (checkbox) e registra decisões
  não óbvias; memória persistente atualizada ao fim do programa.

## II. Ondas (ordem de execução)

### Onda 0 — [P0] Fundação visual (bugs + tema)
- [x] **0.1** Corrigir botões com texto sobreposto: substituir emoji-embutido-no-texto
  por `QIcon` real (ou `QFont.setFamilies` com "Segoe UI Emoji") nos 7 botões de
  `book_details.py:130-174` E nos ~15 botões-emoji da toolbar do leitor
  (`reader_view.py:141-345`). Critério: nenhum QPushButton com emoji no fluxo de texto.
- [x] **0.2** Propagação de tema completa: `_apply_theme` (`main_window.py:332-337`)
  deve alcançar `book_details`, `book_card` e TODOS os diálogos
  (settings/import/collection/flashcards/dossier/wizard/anki). Critério: trocar para
  Light/Sepia atualiza todas as superfícies (teste automatizado por inspeção de
  paleta/stylesheet efetivo).
- [x] **0.3** Migração de estilo: mover os `setStyleSheet` inline de
  `book_details.py`, `book_card.py` e diálogos para `styles.py` central (object-names).
  `rag_panel.py` (48) e `reader_view.py` (40) ficam para a Onda 0b SE o orçamento da
  onda permitir; senão registrar como débito.
- Executores sugeridos: F1 Opus (0.1+0.2), F2 Sonnet (0.3 mecânico), testes por ambos.
- **Registro (2026-07-16, executada):** F1 Opus + F2 Sonnet, sequenciais (whitelists
  compartilhavam book_details/styles). Decisões: (a) `emoji_icon()` em `styles.py`
  pinta emoji em QPixmap 2x → QIcon (fonte "Segoe UI Emoji"/"Noto Color Emoji");
  (b) tema aplicado na `QApplication` → diálogos herdam; (c) seleção do book_card via
  `setProperty("selected")+repolish` em vez de setStyleSheet; (d) 113 estilos inline
  migrados p/ os 3 temas, 5 exceções data-driven mantidas (TagBadge/swatch de cor).
  **Débito Onda 0b — PAGO (ciclo jul/2026-B, PRs #42 e #44, 2026-07-19):**
  180 `setStyleSheet` inline migrados p/ o QSS central nos 3 temas
  (rag_panel/annotation_panel no #42; reader_view/search_overlay/
  proactive_footer/library_view/sidebar/ai_response_card no #44); restam 2
  exceções data-driven documentadas (annotation_panel). Lições registradas
  no QSS: WA_StyledBackground p/ subclasse de QWidget; regra por id não
  cascateia (viewports transparentes); submenus não herdam objectName.
  Débito menor: botão de livro-relacionado e QActions de menus mantêm
  emoji no texto (menus não sofrem o bug — segue como está). Testes novos:
  test_emoji_buttons, test_theme_propagation, test_styles_migration.

### Onda 1 — [P1] Leitor
- [x] **1.1** Botão **Aa** na toolbar: popover com fonte/tamanho/entrelinha/margem/tema
  aplicando AO VIVO (reusa chaves `reader.*` de `settings_dialog.py:135-201`).
- [x] **1.2** Atalhos Space/Shift+Space/PageUp/PageDown + zonas de clique nas laterais
  da página para navegação.
- [x] **1.3** TOC recolhível (toggle 📑 na toolbar; hoje dock fixo 200-300px).
- [x] **1.4** Consolidar 🔊/⏹️/⚙️ num único botão-menu de áudio (prepara o mini-player
  Android).
- [x] **1.5** **Bookmarks de página**: toggle na toolbar + lista (aba no painel TOC);
  tabela nova ou coluna em `reading_progress` (decisão do executor, documentar).
- Executores: F1 Opus (1.1+1.5), F2 Sonnet (1.2+1.3+1.4).
- **Registro (2026-07-16, executada):** decisões: (a) BUG pré-existente corrigido —
  `get_reader_css` ignorava as chaves `reader.*` (a aba Leitor das Configurações não
  tinha efeito); agora aceita tipografia e o ReaderView re-renderiza ao vivo;
  (b) popover Aa = QDialog frameless não-modal (QMenu fecharia no dropdown de fonte e
  ficaria atrás do QWebEngineView); tema usa a chave global `theme` (sem chave nova);
  (c) bookmarks = tabela própria `bookmarks(id, book_id FK, page_number, label,
  created_at, UNIQUE(book_id,page_number))` + add/remove/toggle/get/is em LibraryDB;
  painel lateral virou QTabWidget Sumário/Marcadores; Ctrl+D marca a página;
  (d) Space/Shift+Space/PageUp/PageDown com guarda de foco em campo de texto
  (`_is_text_input_focused`); zonas de clique por terços SÓ no caminho PDF/imagem
  (decisão no release, não engole seleção; guarda de marca-texto adicionada) —
  limitação EPUB/QWebEngineView documentada no código; (e) painel lateral recolhível
  persistido em `reader.side_panel_visible` (default novo no DEFAULT_CONFIG);
  (f) áudio = QToolButton MenuButtonPopup (corpo = Ouvir/Pausar; menu = Parar com
  setEnabled + Configurar vozes); `_audio_stop_btn`/`_tts_settings_btn` removidos
  (grep: sem referências externas). Testes novos: test_bookmarks (10),
  test_reader_typography (11), test_reader_navigation/side_panel/audio_menu (26).
  Débito menor: entrada redundante "⚙️ Voz/Narração" no menu de overflow —
  **PAGO (removida no PR #45, 2026-07-19)**.

### Onda 2 — [P1] Biblioteca
- [x] **2.1** Overlay de % de progresso nos cards (`book_card.py`; dados de
  `reading_progress`), só para progresso>0.
- [x] **2.2** Prateleira "Continuar lendo" no topo de Todos os Livros (progresso>0,
  ordenada por último acesso).
- [x] **2.3** Controle de ordenação no header da biblioteca (hoje só em Config).
- [x] **2.4** Drag-and-drop de importação (`setAcceptDrops` no MainWindow + overlay);
  estado vazio vira alvo de drop com convite.
- [x] **2.5** Menu de contexto (botão direito) nos cards: Abrir, Favoritar, Coleção,
  Metadados, Remover.
- [x] **2.6** Estado "busca sem resultado" distinto de "biblioteca vazia"
  (`library_view.py:200-214`).
- Executores: F1 Opus (2.2+2.4), F2 Sonnet (2.1+2.3+2.5+2.6).
- **Registro (2026-07-16, executada):** decisões: (a) prateleira usa card compacto
  próprio (`_ContinueReadingCard`) com barra de progresso — BookCard 180×300 seria
  alto demais; consulta `get_in_progress_books` (0<pct<99.5, last_read DESC);
  (b) DnD no MainWindow com `DropOverlay` (filho da janela, transparente a mouse);
  drop abre ImportDialog com `initial_files` (API nova retrocompatível) — nunca
  importa direto (preserva opções de OCR); (c) % nos cards via `get_progress_map()`
  em lote (sem N+1) + QProgressBar 4px sob a capa; (d) BUG corrigido: o sort da
  config nunca era aplicado em `_load_library`; combo/asc-desc no header persiste
  nas mesmas chaves `library.sort_*`, e `get_all_books` ganhou WHITELIST de
  colunas/direções (antes interpolava sort_by sem validação — endurecimento de
  segurança); (e) menu de contexto emite `context_action(id, acao)` roteado a
  handlers existentes do MainWindow (zero duplicação); (f) busca vazia mostra
  estado 🔍 próprio (idem filtro "quebrados" — mesma classe de bug). Testes novos:
  63 (continue_reading/drag_drop 23; card_progress/library_sort/context_menu/
  search_empty 40). Débitos menores: combo de sort sem efeito em
  favoritos/status/coleção — **PAGO (PR #45: sort_by/sort_order opcionais
  com whitelist única `_resolve_sort`; opção nova "Última atividade"/
  date_modified preserva a recência legada das visões de status)**;
  prateleira sem menu de contexto — **PAGO (PR #45)**; edge case
  filtro-quebrados-após-busca — **PAGO (PR #47, 2026-07-20: load_books
  desmarca o filtro quando dados novos chegam — cobre a classe inteira,
  não só o caso pós-busca)**.

### Onda 3 — Leitura + IA
- [x] **3.1** **Fontes clicáveis no RAG**: parsear `[Título, p. X]` nas respostas
  (formato já exigido pelo prompt) e navegar o reader ao clique.
- [x] **3.2** **X-Ray da página**: painel/aba com conceitos da página atual + onde mais
  aparecem na biblioteca — SEM LLM (reusa `graph_book_concepts`/`graph_concept_lookup`).
- [x] **3.3** Flashcards enriquecidos: injetar `graph_book_concepts` no gerador; ação
  "gerar cards dos meus destaques" (highlights → P/R em lote com preview).
- [x] **3.4** Word Wise: ação de seleção "definição rápida" (LLM `fast`, resposta curta
  inline no popover).
- [x] **3.5** Cache de tradução por página (padrão fingerprint do dossiê).
- [x] **3.6** Pré-síntese TTS da próxima página em background (corta o gap da leitura
  contínua).
- [x] **3.7** Retomar leitura com mini-resumo da última sessão (reusa dossiê+progresso).
- [x] **3.8** Feedback 👎: baixar limiares (`_MIN_NEGATIVES` 4→2, `_MIN_CATEGORY_HITS`
  3→2) + botão "🔁 Responder de novo considerando isto" imediatamente após o 👎 com
  motivo (reenvia a query com a instrução do motivo no prompt).
- [x] **3.9** Dossiê: injetar progresso/anotações reais do leitor no "perfil".
- Executores: F1 Opus (3.1+3.2), F2 Opus (3.3+3.6+3.7), F3 Sonnet (3.4+3.5+3.8+3.9).
  ATENÇÃO 3.6: threads/timers SÓ na GUI (ADR-006).
- **Registro (2026-07-17, executada; 3 executores sequenciais):**
  (3.1) parser puro `source_citations.py` (regex tolerante p/pp/pág/página; fuzzy
  título→id exato→palavra-inteira→difflib≥0.82); só a LISTA de fontes é clicável —
  linkificar o corpo exigiria trocar QTextEdit streaming por QTextBrowser (débito
  registrado — **PAGO no PR #41, 2026-07-19: QTextBrowser + âncoras
  auto-contidas citation:{book_id}:{page0} pós-stream via Citation.start/end,
  recoloridas na troca de tema**); página do sinal `source_clicked` é 0-based. (3.2) X-Ray = 3ª aba do
  painel lateral; conceitos do livro cacheados 1x, interseção por página eager
  (string matching, `core/xray.py` puro), "onde mais aparece" lazy ao expandir.
  (3.3) `build_study_prompt(concepts=)` retrocompatível; "🃏 Dos destaques" no
  flashcards_dialog com preview editável; teto 40 highlights; `think=False` mantido
  (tarefa fast). (3.6) fronteira ADR-006: `PreSynthesisCache` puro no core +
  `PreSynthesisWorker(QThread)` na GUI; invalidação por nav manual/stop/troca de
  livro/voz; máx 1 página à frente; DÉBITO: reusa helpers privados do TTSRouter
  (síntese-sem-tocar deveria virar API pública). (3.7) `resume_summary.py` puro;
  banner auto-fecha 10s; nunca LLM síncrono ao abrir (dossiê só se cacheado).
  (3.4) `build_word_wise_prompt` puro + worker fast (`think=False`, qualifica);
  popover inline próprio; só seleção ≤4 palavras; só caminho PDF (mesmo escopo do
  SelectionActionPopover — EPUB é débito pré-existente). (3.5) tabela
  `page_translation_cache` (PK book+page+langs, fingerprint sha256 do texto);
  integrado no fluxo texto (`_translate_page_as_text`); fluxo traduzir-e-narrar
  ficou sem cache (débito menor). (3.8) limiares 4→2/3→2 + botão retry via
  `retry_with_reason_requested` prefixando a query no main_window (query RAG normal
  COM thinking; zero mudança no orchestrator). (3.9) perfil real no prompt do
  dossiê; invalidação (a): fingerprint composta grafo+sha256(progresso+n_anotações)
  — 2 leituras SQLite extras por abertura. Testes: +~130 na onda (998→1083).

### Onda 4 — [P2] Higiene e configuração
- [x] **4.1** Aba "Avançado" nas Configurações expondo `graph.*`, `auto_index.*`,
  `translation.*` (`core/config.py:68-96`).
- [x] **4.2** `tts.continuous_translate_reading` no `DEFAULT_CONFIG`.
- [x] **4.3** Diálogo "Atalhos de teclado" (lista os 14+; entrada no menu Ajuda).
- [x] **4.4** Botão Remover no padrão `secondaryBtn`; `ollama_wizard` sem
  `setFixedSize` (mínimos + redimensionável).
- [x] **4.5** Acessibilidade mínima: `setAccessibleName` em todos os botões
  ícone-apenas; tab order curado nas janelas principais.
- Executores: F1 Sonnet (tudo; Opus só se 4.1 complicar).
- **Registro (2026-07-17, executada; 1 executor Sonnet):** (4.1) 5ª aba "Avançado"
  com QScrollArea (21 controles); src/tgt de tradução como QLineEdit (NLLB ~200
  códigos); llm_model vazio↔None. (4.2) chave já era LIDA por reader_view:502 com
  default — só faltava no DEFAULT_CONFIG. (4.3) 18 atalhos publicados, F1 abre o
  diálogo. (4.4) wizard: setFixedSize→setMinimumSize+resize; Remover: DECISÃO —
  mantido `dangerBtn` da Onda 0.3 em vez de `secondaryBtn` (ação destrutiva não
  deve parecer botão comum; o objetivo do item — sair do estilo inline — já fora
  atingido). (4.5) 18 accessibleNames (4 library_view + 14 toolbar do leitor);
  tab order: header da biblioteca + diálogos novos; SearchBar fora (widget irmão
  no main_window). Bônus: corrigido emoji-no-texto do botão "Excluir Selecionados"
  (library_view:289). DÉBITO NOVO identificado: emoji-em-texto remanescente em
  botões de collection_dialog/import_dialog/flashcards_dialog/widgets diversos
  (fora do escopo 0.1) — **PAGO em gui/widgets/* + os 3 diálogos + library_view
  (PR #45, 2026-07-19); restante (sidebar/settings_dialog/ollama_wizard +
  varredura regex global) PAGO no PR #47, 2026-07-20 — débito ZERADO em
  botões**. Testes: +18 (1083→1100 com ajustes).

### Onda 5 — Busca e engajamento
- [x] **5.1** Busca full-text no CONTEÚDO: FTS5 do corpo/OCR (tabela nova alimentada
  pelo indexer em lotes) + modo "buscar no conteúdo" na busca global com trechos.
- [x] **5.2** Estatísticas vivas: streak de dias lidos, minutos/semana (série), meta
  anual opcional (config).
- Executores: F1 Opus (5.1 — cuidado com tamanho do índice/migração), F2 Sonnet (5.2).
- **Registro (2026-07-17, executada):** (5.1) `book_content_fts` FTS5 normal (não
  contentless — snippet() exige texto armazenado; custo ~1x do texto em disco),
  tokenizer `unicode61 remove_diacritics 2`; alimentação na MESMA passada do
  `DocumentIndexerService` (lotes 200 pgs/commit; desvio de whitelist aprovado:
  a extração mora lá, não no rag_engine) e backfill idle 1-por-vez p/ livros
  `indexed_ok`; sanitização palavra→frase-entre-aspas (query maliciosa → vazio,
  nunca exceção, ADR-005); UX: checkbox "No conteúdo" + página de resultados no
  stack com snippets destacados, clique abre livro na página (reusa caminho da
  Onda 3). DÉBITOS: OCR salvo isolado só entra no próximo backfill; livros nunca
  indexados no RAG só ganham FTS quando indexados; sem stemming/prefixo.
  (5.2) tabela `reading_sessions` (UNIQUE book+date, upsert somando segundos)
  alimentada DENTRO de `update_reading_progress` (mesma transação, assinatura
  preservada); streak termina hoje OU ontem (não quebra antes do dia acabar);
  "lido no ano" = read_status + date_modified com bump só na TRANSIÇÃO p/ read
  (contagem retroativa aproximada — documentado); gráfico semanal com QFrames
  (tema via QSS, zero dependência); meta anual `stats.annual_goal_books` (0=off)
  na aba Biblioteca. FOLLOW-UP crítico executado: o tempo real de leitura NÃO era
  medido (time_spent sempre 0 — stats nasceriam mortas); `progress_changed`
  ampliado p/ (book_id, page, total, seconds) [única conexão no projeto],
  cronômetro monotonic por página com cap anti-idle 300s/pág
  (`clamp_session_seconds` puro), flush em fechar/trocar livro; narração
  contínua conta como leitura. LIMITAÇÕES: janela minimizada não pausa —
  **CORRIGIDA (PR #45, 2026-07-19: pausa ao minimizar via changeEvent na GUI +
  `total_elapsed_seconds` puro no core; narração ativa NÃO pausa — modo
  audiobook conta; perda de foco sem minimizar segue contando, cap limita)**;
  StatCard antigo dark-only — **CORRIGIDO (PR #47, 2026-07-20: objectName +
  QSS nos 3 temas, cor por card segue exceção de dado)**.
  Testes: 1100→1201 na onda.

### Onda 6 — OPCIONAL (novidades §4 — exige GO explícito do usuário antes de iniciar)
Vocabulary Builder → Study Guide → Leitura aumentada → Audio Overview local → STT.
NÃO iniciar automaticamente; ao chegar aqui, reportar e perguntar.

## III. Critérios de aceite do programa
1. Ondas 0-5 mescladas na `main`, cada uma com PR próprio e CI verde.
2. Suíte completa verde ao fim de CADA onda (nunca avançar em vermelho) + ruff limpo.
3. Cada feature nova com testes (unitários; GUI via pytest-qt no padrão existente).
4. Zero regressão de tema/layout: teste de propagação de tema criado na Onda 0 passa
   em todas as ondas seguintes.
5. Relatório final consolidado: o que mudou por onda, decisões, débitos registrados,
   e o roteiro do §V pronto para o usuário.

## IV. Orçamentos
- Máx. 10 subagentes por onda; Opus 4.8 para lógica difícil/arquitetura, Sonnet 5
  para mecânica/testes/docs.
- Se o contexto da sessão ficar longo, encerrar a onda corrente, mesclar, atualizar
  este contrato (checkboxes) e continuar em nova sessão a partir dele.

## V. Roteiro de testes reais do usuário (APÓS a entrega — não bloqueia o programa)
1. Temas: alternar Dark/Light/Sepia e varrer biblioteca, detalhes, leitor e todos os
   diálogos (nada preso no escuro; botões legíveis — bug dos sobrepostos morto).
2. Leitor: Aa ao vivo; Space/zonas; TOC recolhível; bookmark em 3 páginas e navegação
   por eles; botão único de áudio; leitura contínua sem gap perceptível entre páginas.
3. Biblioteca: % nos cards; "Continuar lendo" reflete o último livro; drag-and-drop de
   um PDF; menu de botão direito; busca sem resultado mostra estado próprio.
4. IA: pergunta no RAG → clicar numa fonte salta à página; X-Ray da página com
   conceitos reais; 👎 com motivo → "responder de novo" melhora a resposta; flashcards
   de destaques; Word Wise numa palavra; dossiê citando suas anotações.
5. Busca de conteúdo: termo que só existe no corpo de um livro é encontrado.
6. Estatísticas: streak/minutos condizem com o uso da semana.
