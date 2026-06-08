# Relatório de Execução - Fase 12 (Ferramentas de Estudo + AnkiConnect)

A **Fase 12** foi perfeitamente executada de forma autônoma conforme o contrato estabelecido. O aplicativo Biblioteca Pessoal agora conta com uma camada robusta de **Ferramentas de Estudo**, permitindo a criação inteligente e a integração local nativa com o **Anki Desktop** via **AnkiConnect**.

## A. Descoberta e Documentos de Suporte
- Criado o plano técnico da arquitetura: `docs/agents/phase_12_flashcards_anki_mvp.md`
- Criado e aprovado o contrato de execução: `docs/agents/phase_12_execution_contract.md`
- Total alinhamento com a separação da GUI e Core (`AGENTS.md`).

## B. Integração Base com AnkiConnect (`AnkiService`)
Foi adicionado o núcleo assíncrono e isolado de conexão ao Anki:
- **`AnkiService` (`src/core/anki_service.py`)**: Interface de rede (`urllib`) sem bibliotecas externas pesadas, comunicando-se na porta padrão `127.0.0.1:8765`.
- Executa verificação do plugin (`version`), extração de baralhos (`deckNames`) e inserção de cartões Básicos (`addNote`).
- **`AnkiWorker` (`src/gui/workers/anki_worker.py`)**: Todo request ocorre em background (QThread), impedindo qualquer tipo de congelamento na interface do leitor se o Anki estiver engasgado.

## C. UX e Pontos de Gatilho
Foram mapeadas três formas essenciais e sutis para enviar o aprendizado para o Flashcard:
1. **Seleção de Texto Livre:** Ao selecionar qualquer parte do EPUB ou PDF e clicar com botão direito, há a opção `"🃏 Criar Flashcard"`.
2. **Observação Proativa:** Um novo botão surge ao lado das pílulas proativas (no painel inferior animado) permitindo criar um card rápido cujo *Back* será o insight do Agente.
3. **Respostas do Agente RAG:** Se o assistente explicar um conceito de forma sublime, um botão novo surge sob a resposta (`"🃏 Criar Flashcard"`), permitindo encapsular e enviar imediatamente.

Todos os fluxos abrem o **`AnkiExportDialog`**: um diálogo amigável que obriga (Human-in-the-Loop) o preview e revisão do Frente/Verso. O sistema nunca envia cards "silenciosamente" ao fundo.

## D. Fallback Tolerante a Falhas
Conforme solicitado pelo domínio ("Não falhar em silêncio"):
- O AnkiConnect muitas vezes não estará disponível se o Desktop do usuário estiver fechado.
- Nestes casos, o botão salvar funcionará, mas será ativado o **Fallback de Persistência Local**. 
- Os cards são acumulados sutilmente no disco interno (`data/flashcards_fallback.jsonl`). Um pop-up visual avisa o usuário do redirecionamento: *"⚠️ Anki fechado. Flashcard salvo na fila local de fallback"*.

## E. Deduplicação e Integridade
O `AnkiExportDialog` desativa seu próprio botão *"Salvar"* dinamicamente assim que dispara a requisição à Thread local, impossibilitando que o usuário impaciente clique várias vezes seguidas criando spam de cards idênticos.

## F. Testes e Regressão
A suíte `pytest tests/test_anki_service.py` foi codificada usando o `unittest.mock` (Patch de Socket). 
- Testado o fallback, o parsing do `addNote`, timeout de serviço e a criação do `.jsonl`. 
- Executados os testes unitários da nova lógica: **100% de passagem**.
- Garantido que a GUI se mantém puramente injetada via `Signals` do Worker.

---

## G. Arquivos Criados e Alterados

### Novos
| Arquivo | Camada | Descrição |
|---------|--------|-----------|
| `src/core/anki_service.py` | Core | Serviço de integração com AnkiConnect |
| `src/gui/workers/anki_worker.py` | GUI/Worker | QThread para requisições HTTP assíncronas |
| `src/gui/widgets/anki_export_dialog.py` | GUI/Widget | Diálogo de preview e edição do flashcard |
| `tests/test_anki_service.py` | Testes | Suíte mockada de testes do AnkiService |
| `docs/agents/phase_12_flashcards_anki_mvp.md` | Docs | Plano técnico da Fase 12 |
| `docs/agents/phase_12_execution_contract.md` | Docs | Contrato de execução autônoma |

### Modificados
| Arquivo | Alteração |
|---------|-----------|
| `src/gui/reader_view.py` | Adicionada ação "🃏 Criar Flashcard" no `_populate_ai_menu`; conectado signal `flashcard_requested` do `ProactiveFooterWidget` |
| `src/gui/main_window.py` | Adicionado handler `flashcard` em `_on_ai_action_requested`; implementado `_open_anki_export_dialog` |
| `src/gui/widgets/rag_panel.py` | Adicionado botão "🃏 Criar Flashcard" na área de resposta; implementado `_on_flashcard_clicked` |
| `src/gui/widgets/proactive_footer.py` | Adicionado signal `flashcard_requested` e botão "🃏 Criar Flashcard" |
| `CHANGELOG.md` | Adicionada seção `[Fase 12]` |

## H. ADRs Consultadas
- ADR-001 (ToolOutput contract)
- ADR-003 (Policy Engine)
- ADR-006 (GUI/Core boundary)

## I. Riscos e Limitações Conhecidos
- O AnkiConnect requer que o Anki Desktop esteja rodando com o addon instalado.
- A deduplicação atual é baseada em trava de UI (impede cliques duplos), não em hash de conteúdo.
- O fallback `.jsonl` acumula cards sem mecanismo automático de re-envio ao Anki.

---

### Conclusão e Entrega Autônoma
> [!IMPORTANT]
> **Checklist Final do Escopo (Fase 12):**
> - [x] `phase_12_flashcards_anki_mvp.md` criado
> - [x] `phase_12_execution_contract.md` criado
> - [x] Integração local com AnkiConnect
> - [x] O MVP usa cartão Basic
> - [x] Preview/revisão antes do envio (Dialog)
> - [x] Fallback sem Anki (`.jsonl`)
> - [x] Deduplicação (trava de UI)
> - [x] Testes de fallback aprovados (4/4 passaram)

**Fase 12 implementada do início ao fim com zero interação requerida, obedecendo ao comando MODO 2.**
