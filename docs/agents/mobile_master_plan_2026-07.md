# Plano-mestre — Biblioteca Pessoal Mobile (atualização 2026-07-20)

> Sucede e ATUALIZA `docs/mobile-port-analysis.md` e
> `docs/mobile-mvp-proposal.md` (análise de 2026-07-01) com o que os ciclos
> jul/2026-B e jul/2026-C mudaram. Base: `main` `04de387`, 1503 testes.
> Projeto NOVO (repo próprio para o cliente Flutter); o backend vive NESTE
> repo. EXECUTAR SÓ COM GO EXPLÍCITO. Decisões em aberto ao final.

## Decisão de arquitetura (reafirmada da análise de 01/07)

**Cliente-servidor**: núcleo de IA (RAG/TTS/tradução/indexação) fica no PC;
o celular/tablet roda um cliente **Flutter** (Android-first) leve. Empacotar
PyQt6/torch no aparelho segue descartado (sem wheels mobile). Conectividade
Tailscale (ou LAN); auth bearer token estático no MVP. A GUI desktop NÃO
migra — o mobile é REDESENHADO (ver Layout), mantendo o máximo de FUNÇÕES.

## O que mudou A FAVOR desde a análise de 01/07

1. **TTS resolvido**: a consideração nº1 da auditoria ("`speak()` toca
   local via thread — precisa adapter que retorne áudio em buffer") está
   PAGA: `TTSRouter.synthesize_segments()` (PR #54) devolve segmentos
   prontos — a rota `/tts` vira encode WAV/OGG + streaming chunked.
2. **Cache de tradução por página** (PR #53) → `/translate` barato em
   releitura.
3. **FTS com prefixo + backfill imediato** (PR #55) → `/search` melhor.
4. **Lições de startup (B0)**: o backend headless NÃO importa torch no
   boot (lazy, como o TTSInitWorker) e respeita gates do auto-index.
5. **Onda 0b/QSS**: irrelevante p/ mobile (GUI não migra) — confirma que o
   investimento no core é o que transfere.
6. **Sinergia MCP** (`mcp_server_execution_plan_2026-07.md`): MCP e FastAPI
   consomem os MESMOS serviços do core. Se o MCP rodar antes, EXTRAIR uma
   *service layer* comum (`src/services/` ou facade no core) que GUI, MCP e
   API compartilham — decisão a tomar na 1ª rodada de qualquer um dos dois.

## Considerações técnicas da auditoria de 01/07 — estado atual

| # | Item | Estado |
|---|------|--------|
| 1 | speak() toca local → adapter de buffer | **RESOLVIDO** (B2) |
| 2 | `_cancelled` global no RAGEngine | ABERTO — serializar IA no MVP |
| 3 | `constants.py` resolve paths por PROJECT_ROOT | ABERTO — override por env |
| 4 | `opds_server` instancia LibraryDB em nível de módulo | ABERTO — lifespan DI |
| 5 | Core todo bloqueante | ABERTO — threadpools no FastAPI |
| 6 | Reindex bge-m3 bloqueia /search/semantic | ABERTO — gate needs_reindex |

## Mapa de paridade de funções (máximo do desktop no mobile)

| Função desktop | Mobile (como) | Fase |
|---|---|---|
| Biblioteca/grade, coleções, tags, favoritos, sort | `/library` + UI nativa (grid/list, sort da B4/R5 incl. "Última atividade") | M0/M1 |
| Leitor PDF | `pdfrx` client-side (arquivo via `/read`/download progressivo) | M1 |
| Leitor EPUB | spike de renderer Flutter (epub_pro/cosmos_epub — IMATURO, semana 1) | M1 |
| Progresso/cronômetro/streak | `/progress` (regras do core: cap 300s/pág, pausa=app em background — paridade com B0/R5) | M1 |
| Anotações/destaques/marcadores (+ ai_note) | `/annotations` CRUD aditivo | M1 |
| Busca FTS (prefixo) + semântica | `/search?mode=fts|semantic` | M1/M2 |
| Assistente RAG com citações clicáveis | `/rag` SSE (streaming + fontes `[Título, p.X]` resolvidas → deep-link p/ página) | M2 |
| Tradução de página (texto e narrada) | `/translate` (cache B1) | M2 |
| Narração TTS (voz por sentença, perfis) | `/tts` chunked via `synthesize_segments`; player `just_audio`; leitura contínua = cliente pede página seguinte | M2 |
| Word Wise | seleção nativa do renderer → `/wordwise` (LLM fast) | M2 |
| Dossiê + grafo de conceitos + relacionados | `/dossier`, `/related` (caches do core) | M3 |
| Agente proativo | WebSocket `/proactive` | M3 |
| Flashcards/Anki | export server-side; revisão simples no cliente | M3 |
| Importar livros | upload no `/library` + kick FTS (B4) | M3 |
| Estatísticas | `/stats` | M1 |
| OCR, indexação, config de modelos | FICAM NO SERVIDOR (gerenciados pelo desktop) | — |
| OPDS | já existe — mantido p/ apps de leitura de terceiros | — |

## Layout (redesign, não porta)

Navegação por abas inferiores: **Biblioteca · Lendo agora · Assistente ·
Perfil/Stats**. Leitor imersivo (toque nas bordas = virar página — paridade
com as zonas de clique da Onda 1; player de narração persistente estilo
podcast). Tema claro/escuro/sépia com os MESMOS tokens de cor do
`styles.py` (fonte única de paleta — extrair constantes p/ JSON
compartilhável na 1ª rodada de UI). Mockups via Claude Design ANTES de
codar o leitor (diretriz registrada na memória do projeto).

## Fases (rota M0–M5, atualizada)

- **M0 — Backend FastAPI** (neste repo, `src/api/main.py` fino): monta OPDS
  como APIRouter + rotas /library /read /progress /annotations /search
  /stats; auth token; itens 2–6 da tabela acima resolvidos AQUI; testes
  com TestClient sobre core real. (Menor que na análise original graças a
  B2/B4.)
- **M1 — Cliente leitor** (repo novo Flutter): biblioteca + leitor PDF +
  progresso + anotações + busca. Spike EPUB na semana 1 (gate: se renderer
  inviável, EPUB via conversão server-side ou WebView).
- **M2 — IA**: RAG SSE, tradução, TTS streaming, Word Wise.
- **M3 — Proativo + import + flashcards + dossiê.**
- **M4 — Offline parcial**: drift (SQLite local) espelhando
  progresso/anotações com sync; downloads de livros p/ leitura offline.
- **M5 — iOS.**

## Decisões em aberto (usuário)

1. Ordem: **MCP (jul/2026-D) antes do M0** — recomendado (ensaio barato da
   service layer) — ou direto ao M0?
2. Nome/local do repo Flutter novo.
3. Tailscale vs LAN-only no MVP; formato do token.
4. EPUB: aceitar conversão server-side como fallback se o spike falhar?

## Riscos principais

Renderer EPUB Flutter imaturo (gate de spike); concorrência
desktop-aberto × backend (WAL; escrita de índice exclusiva do desktop);
streaming de áudio em rede instável (buffer no cliente); segurança de
upload; escopo de paridade crescer sem gate — TODA função nova entra
primeiro no mapa acima com fase definida.
