# Fluxo de melhorias com feedback de usuários (retomada do desktop)

> Documentado em 2026-07-20 ao fim do ciclo jul/2026-E (pacote v0.1
> distribuído). Este é o processo combinado para a RETOMADA do
> desenvolvimento desktop: o próximo ciclo só abre com feedback coletado e
> GO explícito do usuário.

## 1. Coleta (durante a janela de testes)

- Tester reporta: passo a passo, o que aconteceu × o que esperava, print,
  specs da máquina (Windows, RAM, GPU, **% de escala do monitor**) — o
  molde está no manual (§15) e no LEIA-ME do pacote.
- TODO achado é ANOTADO PRIMEIRO, nunca corrigido no calor do momento.
  Registro canônico: memória `backlog-ajustes-ux` (itens numerados, com
  hipótese técnica junto — padrão dos itens 10–12).
- **Exceção** (precedente do PDF em tofu): defeito que INVALIDA a
  distribuição em si (pacote não abre, artefato corrompido) é corrigido
  imediatamente com o protocolo padrão e o ZIP é regenerado.

## 2. Estado de entrada da retomada (2026-07-20)

| Item | Origem | Hipótese registrada |
|---|---|---|
| 10 — texto cortado em notebook 13" | prints de tester | DPI ≥125% × alturas fixas em px no QSS; reproduzível na dev com escala 150% |
| 11 — TTS degradou até pyttsx3 sem avisar | tester (rodou do REPO) | retestar com o ZIP (Kokoro pré-embutido); falta aviso de degradação |
| 12 — Ollama crasha embeddings (CUDA/PTX) | prints de tester | driver NVIDIA antigo; mitigar com mensagem orientada + sem modal em background |
| "database is locked" no append_chat_turn | validação MCP | conexão lazy do chat history × escritor concorrente (bugs-conhecidos-rag item 11) |
| Pool aprovável: análise de agentes | sessão 2026-07-20 | reranker ONNX, agente de saúde do índice, curador, recap — **só entram com aprovação explícita** |

## 3. Triagem (na retomada, antes de qualquer código)

1. Classificar cada item: **Bloqueador · Bug · UX · Ideia**.
2. Reproduzir localmente quando possível (ex.: escala 150% para o item 10).
3. Agrupar por tema em rodadas coesas (ex.: "rodada DPI", "rodada
   robustez de IA") — nunca uma rodada-colcha-de-retalhos.
4. Apresentar o plano de rodadas ao usuário → **GO**.

## 4. Execução (protocolo padrão, inalterado)

branch → implementação com testes → suíte completa + ruff → PR → auditoria
de 8 ângulos com fixes na rodada → CI → merge (autorização de merge é POR
ciclo, reconfirmada a cada escopo novo).

## 5. Fechamento de cada ciclo de feedback

1. `python -m src.tools.build_package` → novo ZIP.
2. Sanidade do pacote (import + PDF legível — testes já cobrem) e, quando
   houver mudança grande, roteiro de máquina limpa
   (`roteiro_validacao_pacote.md`).
3. Redistribuir aos testers com nota curta de mudanças no LEIA-ME.
4. Atualizar memórias (`backlog-ajustes-ux` com itens fechados, handoff).

## Cadência sugerida

Acumular feedback por janela (1–2 semanas) antes de abrir ciclo — evita
retrabalho e mantém o ZIP dos testers estável. Bloqueadores furam a fila.
