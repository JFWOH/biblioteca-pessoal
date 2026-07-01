# Fase 12 — Ferramentas de Estudo (Flashcards) + Integração Local com Anki (MVP)

## Objetivo
Transformar conteúdo lido em material de estudo reutilizável, oferecendo ao usuário a capacidade de criar flashcards a partir da leitura, interagindo com o Anki Desktop localmente através do AnkiConnect ou caindo em um fallback local se indisponível.

## Escopo
- Integração local com AnkiConnect via API HTTP.
- Criação de cartões do tipo **Basic** (Frente/Verso).
- Origens do cartão: Trecho selecionado, bookmark inteligente, explicação contextual, observação proativa.
- UX: Diálogo de Preview/Revisão para o usuário editar o Front/Back antes do envio.
- Fallback Local: Caso o Anki ou AnkiConnect não estejam disponíveis (timeout, recusa de conexão), os flashcards gerados devem ser enfileirados/armazenados em um arquivo local (ex: `data/anki_fallback.jsonl`) para posterior recuperação ou visualização.
- Testes: Garantir estabilidade na comunicação com a API do AnkiConnect, tratar fallbacks adequadamente e evitar regressões no ReaderView e core AI.

## Fora de Escopo
- Sincronização bidirecional com Anki.
- Gerenciamento completo de agendamento (scheduling/review) dentro da Biblioteca Pessoal.
- Image occlusion e formatos avançados (Cloze não obrigatório).
- Redesign abrangente do leitor.
- Sincronização em nuvem.

## Arquitetura Proposta
- **`src/core/anki_service.py`**: Serviço Core que encapsula chamadas `urllib.request` para a porta default do AnkiConnect (`http://127.0.0.1:8765`). Responsável por checar o health endpoint (`version`), buscar decks (`deckNames`) e adicionar notas (`addNote`). Contém a lógica de fallback (escrever num arquivo local caso o request falhe).
- **`src/gui/workers/anki_worker.py`**: QThread para executar as requisições HTTP e não travar a GUI.
- **`src/gui/widgets/anki_export_dialog.py`**: QDialog limpo e elegante onde o usuário revê a Frente e o Verso gerados.
- **`src/gui/reader_view.py`**:
  - Menu de contexto na seleção de texto para "Criar Flashcard".
  - Botão/Ação na observação proativa e RAG ("Gerar Card").

## Integração com AnkiConnect
- Envia payload JSON via POST para `http://127.0.0.1:8765`.
- Se falhar com `URLError` (Connection Refused), significa que o Anki está fechado.

## Fallback Sem Anki
- Persistência local: As notas não enviadas serão armazenadas em `data/flashcards_fallback.jsonl` com status estruturado para que o usuário saiba que elas existem e possam ser exportadas manualmente.

## Deduplicação
- Impedir múltiplos envios consecutivos da mesma Frente/Verso. O UI botão "Salvar" desabilita após salvar com sucesso.

## Testes
- Testes mockando o servidor do AnkiConnect.
- Testes do `AnkiService` para persistência em fallback.

## Riscos
- **AnkiConnect Ausente:** O fluxo mais comum será o Anki estar fechado. A experiência de fallback deve ser fluída e não emitir alertas irritantes na cara do usuário.
- **Bloqueio da GUI:** Toda rede deve rodar via `QThread`/Worker.

## Critérios de Aceite
- Ao selecionar texto e gerar flashcard, o usuário vê o diálogo de edição.
- Clicar em Salvar cria o card no Anki Desktop (se aberto).
- Se Anki Desktop fechado, salva em disco local e alerta via Toast/StatusBar que foi parar na fila local.
