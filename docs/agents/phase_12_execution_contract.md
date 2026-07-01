# Contrato de Execução - Fase 12 (Ferramentas de Estudo + Anki)

## Status
APROVADA PARA EXECUÇÃO AUTÔNOMA TOTAL.

## Defaults Aprovados
- **Modelo de Integração Principal:** AnkiConnect local (`127.0.0.1:8765`).
- **Cartão Padrão:** Modelo `Basic` (Frente / Verso), pulando templates complexos (Cloze, Image Occlusion).
- **Gatilho (UX):** O usuário deve ativamente clicar para "Criar Flashcard" em áreas compatíveis (seleção de texto, botões em painéis de IA).
- **Revisão Obrigatória:** O card sempre deve ser mostrado na tela em um Diálogo de Preview antes do envio. Criação automática silenciosa (background batch creation) está proibida para evitar sujeira no deck do usuário.
- **Deduplicação:** Impede-se clicks repetidos ou envios duplos do mesmo dialog.
- **Fallback Aprovado:** Local file fallback (ex: `data/flashcards_fallback.jsonl`). Não falhar silenciosamente nem exigir que o Anki inicie.

## Limites de Autonomia
- É PROIBIDO reabrir a discussão sobre qual modelo usar ou se devemos focar na nuvem.
- É PROIBIDO expandir as ferramentas de estudos além de cartões básicos frente/verso.
- Nenhuma alteração arquitetural deve ferir o `AGENTS.md`. Em especial, o `AnkiService` pertence à camada Core e os dialogs/workers pertencem à camada GUI.

## O que NÃO precisa mais ser perguntado
- Posso assumir que o AnkiConnect é a infraestrutura padrão local? **Sim**.
- Preciso perguntar se o fallback local é suficiente? **Não**.
- Posso pular cloze/image occlusion? **Sim**.

## Restrições de Segurança
- Não armazenar segredos (o AnkiConnect não exige auth por padrão quando acessado de `localhost`).
- Tratar o endpoint como não garantido (pode ocorrer timeout, connection refused).
- Não bloquear a interface; toda chamada de rede deve ocorrer via `QThread`.

## Planto de Rollback
- Se a integração com AnkiConnect gerar erros sistêmicos que afetem o RAG ou a renderização do leitor, a feature deve ser "comentada" ou o botão "Criar Flashcard" desabilitado na UI.
- Nenhuma modificação desta fase é destrutiva ao banco de dados SQLite existente.
