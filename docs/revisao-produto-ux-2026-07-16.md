# Revisão de Produto & UX — Biblioteca Pessoal (2026-07-16)

Fecha a última revisão de funcionalidades do desktop e prepara dois insumos
seguintes: **(a)** o ajuste final de layout (pacote executável no §5 desta
revisão) e **(b)** a base de produto da versão Android — ver
`docs/mobile-mvp-proposal.md` e `docs/mobile-port-analysis.md`.

**Estado do código:** `main` pós-PR #14 (aprendizado 👍/👎 do RAG mesclado).
PRs abertos: **#12** (Fase 5 — proativo com continuidade) com **#13** (Fase 6
— aprendizado com dispensas) empilhado sobre ele; **#18** (fix de teardown do
chromadb nos testes).

**Método:** 3 auditorias somente-leitura (2 Opus + 1 Sonnet) cobrindo UX vs
mercado, valor de IA por feature e inventário de layout, seguidas de
síntese/validação do orquestrador. O app **não foi executado** — todos os
achados vêm de leitura estática de código; ver ressalvas no §7.

---

## 1. UX vs mercado

Comparação contra Calibre, KOReader/Moon+, Kindle/Apple Books, Readwise
Reader e Zotero.

### 1.1 No nível ou acima do mercado

| # | Recurso | Evidência | Onde supera/iguala |
|---|---|---|---|
| 1 | Popover de seleção com 6 ações de IA em 1 clique | `src/gui/widgets/selection_popover.py:21-27` | Iguala/supera o Ghostreader, 100% local |
| 2 | RAG agentic com fontes + PolicyEngine + aprendizado 👍/👎 com motivo | `main_window.py:477-504`, `core/feedback_learning.py` | Acima do padrão consumer |
| 3 | Agente proativo de insights | `src/gui/proactive_reader_service.py`, `widgets/proactive_insights_panel.py` | Nem Kindle nem Readwise têm |
| 4 | TOC com miniaturas de capítulo | `reader_view.py:753-757` | Acima de Kindle/Apple Books |
| 5 | TTS neural local multi-engine/estilo com leitura contínua | `settings_dialog.py:295-314`, `core/tts/tts_router.py` | — |
| 6 | Dossiê + grafo com livros relacionados | `book_details.py:27-28`, `core/graph/` | — |
| Extra | Retoma na última página aberta | `main_window.py:437-438` | — |

### 1.2 Lacunas priorizadas

Ordem de prioridade (1 = maior impacto). Cada linha liga o padrão de mercado
ausente à evidência no desktop, à correção proposta e à implicação para o
Android.

| # | Padrão de mercado ausente | Evidência (desktop) | Correção (desktop) | Implicação Android |
|---|---|---|---|---|
| 1 | Tipografia enterrada em Config; sem "Aa" no leitor | Toolbar só tem zoom (`reader_view.py:167-181`); controles em `settings_dialog.py:135-201` | Botão Aa com popover ao vivo | Bottom-sheet Aa (mobile-mvp §4 já marca dynamic type como crítico) |
| 2 | Cards sem % de progresso | `book_card.py:103-122`; `ReadingProgressBar` só existe no leitor (`reader_view.py:511`) | Overlay de barra fina no card — dado já existe em `reading_progress` | Alimenta a Home mobile |
| 3 | Sem prateleira "Continuar lendo" | Default = todos por data de adição (`main_window.py:345-348`) | Linha no topo ordenada por `last_read` | Vira a tela Home primária do Android |
| 4 | Sem bookmarks de página | Só `is_favorite` por livro (`database.py:48,304`) | Toggle + lista no painel TOC | Long-press no Android |
| 5 | Navegação sem Space/PageDown/zonas de clique | Só ◀▶ e setas (`reader_view.py:140-164,545-548`) | Adicionar atalhos + zonas de clique | Zonas de toque mandatórias no Flutter |
| 6 | Sem busca full-text no CONTEÚDO | FTS5 indexa só title/author/description (`database.py:212-214`); Ctrl+F é por documento | Índice FTS do corpo/OCR | Keyword on-device + semântica no servidor (alinhar com o MVP) |
| 7 | Estatísticas estáticas, sem streak/meta | `stats_panel.py:91-140` | Streak + minutos/semana + meta anual | Gancho de engajamento/notificação no mobile |
| 8 | Sem drag-and-drop de importação | Zero `acceptDrops` em `src/gui` | `setAcceptDrops` + overlay | Share intent no Android |
| 9 | Sem menu de contexto nos cards | `book_card.py:21-22` só expõe `clicked`/`double_clicked` | `QMenu` no botão direito | Long-press menu |
| 10 | Estado vazio aponta para o menu em vez de convidar ao drop | `library_view.py:176` | Ver P1 no §5 (mesmo overlay do item 8) | — |

---

## 2. Veredito por feature de IA

| Feature | Ganho | Justificativa | Ajuste que eleva |
|---|---|---|---|
| Chat RAG agentic | **ALTO** | Perguntar aos próprios livros com citação obrigatória `[Título, p. X]`; custo de dezenas de segundos | Fontes CLICÁVEIS que saltam à página; avaliar `max_rounds` 5→3 |
| Feedback 👍/👎 + chips | **BAIXO/MÉDIO** isolado | Bem construído, mas limiares (≥4 negativos ou ≥3 por categoria) raramente disparam com 1 usuário só | Baixar limiares + oferecer "responder de novo considerando isto" logo após o 👎 |
| Proativo | **MÉDIO** hoje na `main`* | Stateless, vê só a página atual; latência alta com raciocínio; em nível "Estudo"/1 página vira ruído caro | Ver nota abaixo |
| Dossiê | **MÉDIO/ALTO** | Cache por fingerprint resolve a latência; "perfil do leitor" ainda raso | Injetar progresso/anotações reais |
| Flashcards + Anki | **ALTO** para estudo | Modelo fast, preview, fallback `.jsonl` | Gerador não usa o grafo — injetar `graph_book_concepts`; gerar cards a partir de highlights |
| Grafo | **MÉDIO** | Infra de alto valor, exposição baixa — hoje é invisível ao usuário | "X-Ray da página" sem LLM, reusando `graph_book_concepts`/`graph_concept_lookup` |
| Tradução seleção/página + narração | **ALTO** | NLLB local + revisão por LLM | Cache por página + Word Wise inline |
| TTS multilíngue | **ALTO** | Detecção de idioma, Kokoro→Piper, leitura contínua | Pré-sintetizar a próxima página |
| Roteamento fast/deep | **MÉDIO** indireto | "fast" hoje é o mesmo e4b com `think=False`, por benchmark de 2026-07-06 | Considerar um modelo pequeno real para tarefas triviais |

\* **Correção do orquestrador sobre o Proativo:** a continuidade (Fase 5) e o
aprendizado com dispensas (Fase 6) **já estão implementados** nos PRs
#12/#13, pendentes de merge. A crítica do auditor à versão da `main` (sem
continuidade, sem aprendizado) na prática **confirma o valor desses PRs** —
não é um problema novo a resolver, é o problema que eles já resolvem.

Sobre latência: a opção `think=False` no proativo contraria uma decisão já
registrada do usuário (2026-06-29 — qualidade > velocidade no proativo;
`think=False` ali já foi tentado e revertido por regressão). Registrar como
**tradeoff aberto**, não como recomendação fechada: (a) manter raciocínio e
mitigar via continuidade/frequência, ou (b) `think=False` restrito aos níveis
de alta frequência (ex.: "Estudo").

**Achado transversal positivo:** todas as recomendações da revisão de
engenharia de 2026-07-05 já foram executadas — `keep_alive` em
`ollama_defaults.py`, feedback de raciocínio, cache de dossiê, demarcação de
conteúdo web, roteamento por tarefa. O app está mais maduro do que aquela
revisão sugeria.

---

## 3. Melhorias de leitura+IA priorizadas

Ordenado por valor ÷ esforço. Esforço: P = pequeno, M = médio, G = grande.

| # | Melhoria | Esforço/Valor | Mecanismo / infra reusada |
|---|---|---|---|
| 1 | Fontes clicáveis no RAG | P, alto | Parsear `[Título, p. X]` (já exigido pelo prompt) e navegar o reader |
| 2 | Mesclar PRs #12/#13 após validação do usuário | P, alto | Entrega continuidade + aprendizado já prontos |
| 3 | X-Ray da página | M, alto | Conceitos da página + onde mais aparecem, sem LLM (grafo) |
| 4 | Botão Aa no leitor | M | Fecha a lacuna nº 1 de UX (§1.2) |
| 5 | Flashcards do grafo + de highlights | M | `graph_book_concepts` |
| 6 | Continuar lendo + progresso nos cards | P/M | `reading_progress` |
| 7 | Pré-síntese TTS da próxima página | M | `tts_router` |
| 8 | Cache de tradução por página | P | — |
| 9 | Word Wise por seleção | P/M | Popover de seleção existente |
| 10 | Retomar com mini-resumo da última sessão | M | Reusa dossiê + progresso |

---

## 4. Novidades propostas

Não-gadget: cada item resolve um problema real observado nas seções
anteriores, com paralelo de mercado explícito.

| # | Novidade | Esforço | Problema real | Paralelo de mercado |
|---|---|---|---|---|
| 1 | Audio Overview local | M/G | Resumo em áudio do livro/tema via RAG/dossiê + TTS | NotebookLM |
| 2 | Perguntar por voz / STT local | M | Fecha o ciclo com o TTS existente — hoje não há STT no código | — |
| 3 | Vocabulary Builder | P/M | Palavra consultada vira card SRS automático | Kindle |
| 4 | Leitura aumentada | M | "Livros que conversam com esta página" via `related_books`/`cross_reference` | Recall |
| 5 | Study Guide por livro | M | Perguntas de revisão + resumo por capítulo | NotebookLM/Ghostreader |

---

## 5. Plano do ajuste final de layout

Pacote executável desta revisão — o que sai desta rodada para implementação.

### 5.1 [P0] Bugs e fundação

**(a) Botões sobrepostos no `book_details`.** Causa provável: emoji embutido
como texto em `QPushButton` com fonte "Segoe UI" sem fallback de emoji
(`main.py:35-36`; `book_details.py:130-174`). Correção: `QIcon` real +
`setText` puro (ou `QFont.setFamilies` incluindo "Segoe UI Emoji"). O mesmo
padrão está latente em ~15 botões-emoji da toolbar do leitor
(`reader_view.py:141-345`). Diagnóstico de confiança média — não reproduzido,
ver §7.

**(b) Propagação de tema quebrada.** `_apply_theme` (`main_window.py:332-337`)
só notifica 3 widgets — `book_details`, `book_card` e **todos os diálogos**
ficam presos ao tema escuro quando o usuário escolhe Light ou Sepia.

**(c) Migração dos `setStyleSheet` inline.** 324 ocorrências espalhadas por 27
arquivos (maiores: `rag_panel` com 48, `reader_view` com 40,
`annotation_panel` com 34). Plano: consolidar em `styles.py` central,
começando por `book_details`/`book_card`/diálogos — são os que mais sofrem
com o bug de tema do item (b).

### 5.2 [P1] Os 8 ajustes de UX

- Botão **Aa** no leitor (tipografia acessível em 1 clique).
- **Progresso** nos cards da biblioteca.
- Prateleira **"Continuar lendo"**.
- **TOC recolhível** — hoje é um dock fixo de 200-300px (`reader_view.py:428-432`).
- **Ordenação no header** da biblioteca — hoje só existe em Config (`settings_dialog.py:120-127`).
- Consolidar **🔊/⏹️/⚙️ de TTS** num botão-menu único — a toolbar tem hoje ~14 controles; isso também prepara o mini-player do Android.
- **Atalhos de teclado** (Space/Shift+Space/PageUp/PageDown) + **zonas de clique** na página.
- **Drag-and-drop** com overlay — o estado vazio (item 10 do §1.2) vira alvo de drop.

### 5.3 [P2] Higiene

- Distinguir estado **"busca sem resultado"** de **"biblioteca vazia"** (`library_view.py:200-214`).
- Tela ou diálogo de **referência de atalhos** — hoje nenhum lugar lista os 14+ atalhos existentes.
- Aba **"Avançado"** nas Configurações, expondo os flags hoje sem UI (`graph.*`, `auto_index.*`, `translation.*` em `core/config.py:68-96`).
- Adicionar `tts.continuous_translate_reading` ao `DEFAULT_CONFIG` — hoje é lido em `reader_view.py:378-379` mas está ausente do esquema.
- Padronizar o botão **Remover** no `secondaryBtn` (`book_details.py:167-172`).
- `ollama_wizard` sem `setFixedSize(520,420)`.
- **Acessibilidade mínima**: `setAccessibleName` nos botões ícone-apenas; curadoria de tab order — hoje zero `setTabOrder`/`setFocusPolicy` em `src/gui`.

---

## 6. Implicações para a versão Android

A arquitetura do MVP mobile (cliente-servidor, núcleo no PC) está correta:
`bge-m3`/Chroma (65k chunks) e NLLB permanecem no servidor — não fazem
sentido on-device.

**Ordem de porte da IA:**

1. **Primeiro (M2):** TTS streaming, tradução de seleção/página, chat RAG com
   fontes clicáveis, busca semântica.
2. **Cedo e barato:** dossiê + X-Ray (cacheados por fingerprint no servidor),
   flashcards.
3. **Depois, com ressalva:** proativo — repensar a frequência em mobile
   (bateria/atenção); só faz sentido portar após a continuidade das Fases
   5/6 estar validada no desktop. Os chips de feedback vão de carona no RAG.
4. **Não portar on-device:** embeddings/vector store e NLLB.

**UI mobile derivada das lacunas do §1:** Home = "Continuar lendo" + progresso
nos cards; leitor com zonas de toque, bottom-sheet Aa, long-press para
bookmark/menu; share intent para importar; streak/metas como gancho de
engajamento.

---

## 7. O que esta revisão NÃO cobriu

- **App não executado** — tudo é leitura estática de código; o bug dos
  botões sobrepostos (§5.1a) é diagnóstico de confiança média, não
  reproduzido.
- **Qualidade real de saída** dos modelos (relevância do RAG, dos flashcards,
  da tradução) não foi avaliada.
- **Acessibilidade** não foi medida (contraste WCAG, leitores de tela).
- **Performance** não foi medida — números de latência citados vêm de
  documentos/comentários pré-existentes, não de novas medições.
- **Temas Light/Sepia** não foram inspecionados visualmente.
- **Readers** (parsing de PDF/EPUB) e a **suíte de testes** ficaram fora do
  escopo.
- **Comparativos de mercado** limitados a ~10 buscas web; Perplexity, Elicit
  e outros concorrentes de pesquisa não foram cobertos.
- **Gestos mobile** foram inferidos dos documentos de MVP, não testados em
  dispositivo.
