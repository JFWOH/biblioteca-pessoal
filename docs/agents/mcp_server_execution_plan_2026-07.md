# Plano de execução — Servidor MCP da Biblioteca Pessoal (ciclo jul/2026-D)

> Preparado em 2026-07-20 ao fim do ciclo jul/2026-C. Base: `main` `04de387`,
> suíte 1503 passed. EXECUTAR EM SESSÃO NOVA com GO explícito do usuário.
> Protocolo: o mesmo dos ciclos B/C (branch → executor ou inline → suíte
> completa + ruff → PR → auditoria de 8 ângulos → CI → merge automático se
> reconfirmado). Gotchas de sessão: memória `handoff-sessao-jul2026`.

## Objetivo

Expor o app a uma LLM do usuário (Claude Desktop/Code ou outro host MCP)
via servidor **MCP local (stdio)**, para: explorar biblioteca e notas,
agregar conhecimento à inteligência local (`ai_note`), consultar o RAG
local como ferramenta, e utilitários (tradução/áudio).

## Arquitetura

- **Novo** `src/mcp/server.py` (+ `src/mcp/tools/*.py` se crescer):
  processo standalone headless, transporte **stdio**, SDK oficial `mcp`
  (padrão FastMCP: `@mcp.tool`/`@mcp.resource`/`@mcp.prompt`).
  **Pinar SDK v1**; migração à v2 (spec 2026-07-28) é rodada própria
  posterior.
- Importa SÓ `src/core/**` (ADR-006 garante zero Qt) + serviços puros.
  NENHUM import de `src/gui/**`.
- SQLite: abrir com **WAL + busy_timeout** (o `_write_lock` do LibraryDB é
  in-process; concorrência com o app aberto é cross-process). Chroma:
  leitura concorrente ok; ESCRITA de índice segue exclusiva do app
  (o MCP não indexa).
- Registro no host: `claude mcp add biblioteca -- <venv>\python.exe -m
  src.mcp.server` (documentar no README + aba "Integrações" futura).

## Rodada M1 — read-only (valor imediato, risco mínimo)

Ferramentas: `list_books` (filtros/sort via `_resolve_sort`), `get_book`,
`search_books`, `search_content` (FTS5 c/ prefixo, snippets),
`semantic_search` (Chroma/bge-m3), `get_page_text(book_id, first, last)`
**com teto de 10 páginas/chamada**, `list_annotations`,
`export_annotations_markdown`, `library_stats` (streak/minutos/fts_stats).
Resources: `biblioteca://book/{id}/annotations`, `biblioteca://stats`.

Testes: unitários sobre as funções-ferramenta (chamam o core com
LibraryDB real em tmp_path — sem processo MCP); 1 teste de integração
in-process com client session do SDK (stdio pipes) validando
list/search/get. Guarda estrutural: `src/mcp/**` não importa PyQt6/gui.

## Rodada M2 — escrita guardada + ponte com o RAG

- Config novo `mcp.allow_writes` (default **False**); ferramentas de
  escrita retornam erro claro quando desligado.
- `add_annotation(book_id, page, content, title=None)` → SEMPRE tipo
  `ai_note` com origem `source:"mcp"` gravada (campo/convenção a definir
  lendo o schema de annotations — não inventar coluna sem checar).
- `tag_book`, `add_to_collection`, `create_collection`,
  `set_reading_status`, `toggle_favorite`.
- **PROIBIDO**: qualquer delete/update destrutivo. Não expor.
- `ask_library(question, book_id=None)` → RAG local (Ollama+Chroma) com
  citações resolvidas (`source_citations`). ATENÇÃO aos gotchas do RAG:
  flag `_cancelled` global no engine (serializar chamadas — 1 por vez,
  lock) e `needs_reindex()` → erro amigável em vez de resposta errada.
  Timeout generoso + mensagem sobre o thinking do gemma (minutos são
  normais — ver handoff).

## Rodada M3 (opcional) — utilitários e polimento

- `translate(text)` (NLLB + cache de página quando aplicável),
  `synthesize_audio(text)` → `TTSRouter.synthesize_segments` (API pública
  da B2) → WAV em arquivo temporário, retorna caminho.
- Prompts: `estudar_livro(book_id)` (destaques + dossiê → prompt pronto).
- Migração SDK v2 se já estável.

## Segurança (invariantes de TODAS as rodadas)

stdio apenas (sem rede); leitura por padrão; escrita atrás de flag e
aditiva; teto de páginas por chamada; nenhuma ferramenta destrutiva;
origem `mcp` em tudo que escrever.

## Riscos conhecidos

Concorrência cross-process com o app aberto (WAL mitiga; documentar);
RAG serializado (gotcha `_cancelled`); Ollama é servidor compartilhado
(ok); startup do processo MCP NÃO deve importar torch/kokoro
antecipadamente (lição B0 — lazy import; só M3 usa TTS).

## Fora de escopo

Transporte HTTP/remoto (é o M0 do mobile — ver
`mobile_master_plan_2026-07.md`; extrair service layer comum é decisão
daquele plano); UI de configuração rica; elicitation/sampling do MCP.
