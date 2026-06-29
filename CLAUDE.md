# Project Guidelines & AI Behavior

Follow these core principles for every task:

1. **Ask, don't assume:** If something is unclear, ask before writing a single line. Never make silent assumptions about intent, architecture, or requirements.
2. **Simplest solution first:** Always implement the simplest thing that could work. Do not add abstractions or flexibility that weren't explicitly requested.
3. **Don't touch unrelated code:** If a file or function is not directly part of the current task, do not modify it, even if you think it could be improved. Clean up only your own mess.
4. **Flag uncertainty explicitly:** If you are not confident about an approach or technical detail, say so before proceeding. End every task by explicitly stating what you did NOT do or cover.

---

## Governança (fonte de verdade)

- Regras de execução de agentes: **`AGENTS.md`** (orquestração, segurança, reporting).
- Decisões de arquitetura: **`.agents/adr/`** — leia o(s) ADR(s) do subsistema antes de mexer:
  ADR-001 (ToolOutput uniforme), ADR-002 (AgentState explícito), ADR-003 (PolicyEngine),
  ADR-004 (TraceLogger), ADR-005 (degradação graciosa), ADR-006 (fronteira GUI↔Core AI),
  ADR-007 (Audio Reader / TTS local).
- **ADR-006 (crítico):** `src/core/**` NÃO importa PyQt6/GUI. Threads/sinais/timers ficam em
  `src/gui/**`; o core expõe serviços/contratos puros.

## Ambiente (Windows — usar SEMPRE o venv do projeto)

- Há vários Pythons no PATH (inclusive um venv quebrado em `H:`). Use **sempre**
  `venv\Scripts\python.exe` — nunca `python` solto.
- Rodar o app: `iniciar.bat` ou `venv\Scripts\python -m src.main`.
- Rodar testes: `venv\Scripts\python -m pytest tests/ -q`.
- Lint: `venv\Scripts\python -m ruff check <arquivo>` (config em `pyproject.toml`).

## Definition of Done

- Uma tarefa só termina com **testes relevantes verdes** (foco primeiro, depois a suíte).
  Se não der para rodar (dependência/ambiente), reporte o bloqueio exato e não declare sucesso.
- **Relatório final obrigatório** (espelha AGENTS.md §Reporting): arquivos alterados, testes
  rodados + resultado, ADRs consultados, riscos/limitações, e o que NÃO foi coberto.
- Commits: prefixo convencional (feat/fix/docs/chore/refactor), em branch a partir de `main`,
  terminando com `Co-Authored-By: Claude ...`. Commitar/pushar só quando solicitado.

## Gotchas confirmados (evitar re-descobrir)

- **Embeddings = `bge-m3`** (1024d) no Chroma. Trocar de modelo exige reindex: `RAGEngine.needs_reindex()`
  detecta divergência de dimensão e `reset_collection()` recria a coleção.
- **`HF_HUB_OFFLINE` é constante de módulo do `huggingface_hub`** (lida no import). Para baixar
  um asset no 1º uso, patche `huggingface_hub.constants.HF_HUB_OFFLINE = False` ao redor do load
  (mudar só `os.environ` NÃO basta). Ver `KokoroProvider._ensure_voice` e `nllb_backend`.
- **GPU = Blackwell/sm_120** com `torch cu128`. Seleção de device por `torch.cuda.get_arch_list()`;
  fallback automático para CPU em GPU não suportada (degradação graciosa).
- **OCR = RapidOCR (ONNX)**, sem binário de sistema (não usar Tesseract).
- **TTS:** narração detecta idioma (PT/EN) e resolve a voz por idioma; Kokoro (padrão) → Piper (fallback).
