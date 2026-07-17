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
  **Débito Onda 0b:** `rag_panel.py` (48), `reader_view.py` (40),
  `annotation_panel.py` (34), `search_overlay.py` (14), `proactive_footer.py` (14),
  `library_view.py` (12), `sidebar.py` (6) seguem com estilos inline. Débito menor:
  botão de livro-relacionado (`book_details.refresh_graph_section`) e QActions de
  menus mantêm emoji no texto (menus não sofrem o bug). Testes novos:
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
  Débito menor: entrada redundante "⚙️ Voz/Narração" no menu de overflow mantida.

### Onda 2 — [P1] Biblioteca
- [ ] **2.1** Overlay de % de progresso nos cards (`book_card.py`; dados de
  `reading_progress`), só para progresso>0.
- [ ] **2.2** Prateleira "Continuar lendo" no topo de Todos os Livros (progresso>0,
  ordenada por último acesso).
- [ ] **2.3** Controle de ordenação no header da biblioteca (hoje só em Config).
- [ ] **2.4** Drag-and-drop de importação (`setAcceptDrops` no MainWindow + overlay);
  estado vazio vira alvo de drop com convite.
- [ ] **2.5** Menu de contexto (botão direito) nos cards: Abrir, Favoritar, Coleção,
  Metadados, Remover.
- [ ] **2.6** Estado "busca sem resultado" distinto de "biblioteca vazia"
  (`library_view.py:200-214`).
- Executores: F1 Opus (2.2+2.4), F2 Sonnet (2.1+2.3+2.5+2.6).

### Onda 3 — Leitura + IA
- [ ] **3.1** **Fontes clicáveis no RAG**: parsear `[Título, p. X]` nas respostas
  (formato já exigido pelo prompt) e navegar o reader ao clique.
- [ ] **3.2** **X-Ray da página**: painel/aba com conceitos da página atual + onde mais
  aparecem na biblioteca — SEM LLM (reusa `graph_book_concepts`/`graph_concept_lookup`).
- [ ] **3.3** Flashcards enriquecidos: injetar `graph_book_concepts` no gerador; ação
  "gerar cards dos meus destaques" (highlights → P/R em lote com preview).
- [ ] **3.4** Word Wise: ação de seleção "definição rápida" (LLM `fast`, resposta curta
  inline no popover).
- [ ] **3.5** Cache de tradução por página (padrão fingerprint do dossiê).
- [ ] **3.6** Pré-síntese TTS da próxima página em background (corta o gap da leitura
  contínua).
- [ ] **3.7** Retomar leitura com mini-resumo da última sessão (reusa dossiê+progresso).
- [ ] **3.8** Feedback 👎: baixar limiares (`_MIN_NEGATIVES` 4→2, `_MIN_CATEGORY_HITS`
  3→2) + botão "🔁 Responder de novo considerando isto" imediatamente após o 👎 com
  motivo (reenvia a query com a instrução do motivo no prompt).
- [ ] **3.9** Dossiê: injetar progresso/anotações reais do leitor no "perfil".
- Executores: F1 Opus (3.1+3.2), F2 Opus (3.3+3.6+3.7), F3 Sonnet (3.4+3.5+3.8+3.9).
  ATENÇÃO 3.6: threads/timers SÓ na GUI (ADR-006).

### Onda 4 — [P2] Higiene e configuração
- [ ] **4.1** Aba "Avançado" nas Configurações expondo `graph.*`, `auto_index.*`,
  `translation.*` (`core/config.py:68-96`).
- [ ] **4.2** `tts.continuous_translate_reading` no `DEFAULT_CONFIG`.
- [ ] **4.3** Diálogo "Atalhos de teclado" (lista os 14+; entrada no menu Ajuda).
- [ ] **4.4** Botão Remover no padrão `secondaryBtn`; `ollama_wizard` sem
  `setFixedSize` (mínimos + redimensionável).
- [ ] **4.5** Acessibilidade mínima: `setAccessibleName` em todos os botões
  ícone-apenas; tab order curado nas janelas principais.
- Executores: F1 Sonnet (tudo; Opus só se 4.1 complicar).

### Onda 5 — Busca e engajamento
- [ ] **5.1** Busca full-text no CONTEÚDO: FTS5 do corpo/OCR (tabela nova alimentada
  pelo indexer em lotes) + modo "buscar no conteúdo" na busca global com trechos.
- [ ] **5.2** Estatísticas vivas: streak de dias lidos, minutos/semana (série), meta
  anual opcional (config).
- Executores: F1 Opus (5.1 — cuidado com tamanho do índice/migração), F2 Sonnet (5.2).

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
