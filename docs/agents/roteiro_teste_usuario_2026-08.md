# Roteiro de teste do usuário — versão de teste ago/2026 (rodada UX & Otimização)

**Para você (Jeferson) e/ou o tester.** Esta versão fecha a rodada de polimento de
UX + otimização de leitura e IA (contrato e evidências em
`docs/agents/rodada_ux_otimizacao_2026-08_execution_contract.md` e
`rodada_ux_2026-08_registro.md`). O seu feedback sobre ESTA versão define a próxima.

**Pacote:** `BibliotecaPessoal.zip` (gerado por `build_package` com Kokoro E a voz de
reserva do Piper embutidos). Instalação: extrair e dar 2 cliques em "Biblioteca
Pessoal" — o roteiro completo de máquina limpa continua sendo
`docs/agents/roteiro_validacao_pacote.md` (17 itens, nunca executado em máquina limpa:
segue pendente e vale a pena fazer nesta versão).

---

## 1. O que você deve SENTIR de diferente (sem procurar nada)

- [ ] **Abrir o app**: janela aparece bem mais rápido (medido: import 2,1s → 0,5s;
  janela offscreen 2,7s → 1,1s). O torch não carrega mais no startup.
- [ ] **Abrir PDF grande**: o sumário aparece NA HORA (as miniaturas chegam em
  seguida, sem congelar; antes travava ~1,2-1,5s). Reabrir o mesmo livro: miniaturas
  instantâneas (cache em disco).
- [ ] **Narração**: warmup do Kokoro agora espera o app assentar (1,5s após o fim da
  carga) — o startup não disputa CPU com o TTS.
- [ ] **Chat da biblioteca**: primeira pergunta depois de horas com o app aberto não
  deve mais vir "fria" (re-aquecimento ao focar o chat). Enquanto a IA pensa, você vê
  um esqueleto animado e depois pode expandir "▸ N passos" no cartão da resposta.

## 2. Itens do SEU feedback de julho — verificar um a um

- [ ] **(item 10) Notebook 13"/DPI**: abrir Configurações → as 6 abas aparecem
  (inclusive "🔊 Narração")? Nada de texto cortado nas abas Leitor/Biblioteca/
  Integrações (agora têm rolagem)? **Este é o item que SÓ a sua máquina confirma** —
  se ainda cortar algo, print + em qual aba/controle.
- [ ] **(item 11) TTS**: no menu rápido de narrador, o pyttsx3 agora é o ÚLTIMO
  ("Legado — qualidade inferior"). Se a narração cair para um motor reserva, aparece
  aviso na barra de status + ⚠️ no botão de áudio. Teste: narrar uma página normal
  (deve ser o Kokoro, sem aviso).
- [ ] **(item 12) Sem modais intrusos**: reindexar a biblioteca com IA e, se der erro
  (ex.: driver), a mensagem vai para a barra de status/painel — NENHUMA janelinha
  modal deve pular durante tarefa de fundo. Erro de GPU antigo agora explica o que
  fazer (atualizar driver ou Ollama em CPU).

## 3. Novidades pequenas para experimentar

- [ ] **"Simplificar"** ao selecionar um trecho (menu e barrinha) — explicação em
  linguagem simples, curta.
- [ ] **Barrinha de ações no EPUB**: selecionar um trecho LONGO num EPUB agora abre a
  mesma barra do PDF (antes só o menu de contexto).
- [ ] **"✨ Leitura confortável"** no popover de tipografia (Aa) — um clique aplica
  fonte maior + respiro; outro clique restaura.
- [ ] **Chips de perguntas** acima do campo do chat com um livro aberto (vêm dos
  conceitos do X-Ray; some se o livro não tem grafo).
- [ ] **Arquivo corrompido**: tentar abrir um PDF/EPUB quebrado deve dar aviso claro
  na barra de status, nunca travar/estourar.
- [ ] **Reserva de voz**: com a internet DESLIGADA logo após instalar, "Ouvir página"
  deve funcionar (Kokoro embutido); a reserva Piper pt-BR também está no pacote
  (`data\piper\models\`).

## 4. Opcional (destrava otimização extra de IA)

- [ ] Rodar `ollama pull qwen3.5:4b` (3,4GB). Com ele instalado, as tarefas rápidas
  de IA (conceitos, flashcards) passam a usar um modelo que COEXISTE com o de chat na
  VRAM — some a recarga de ~8GB ao alternar. Sem ele, tudo segue como antes.

## 5. Validações antigas que continuam com você (nunca executadas)

- [ ] Roteiro de máquina limpa (`roteiro_validacao_pacote.md`) — 17 itens.
- [ ] MCP no host real (Claude Desktop/Code): registrar e usar `ask_library` com o
  app aberto ao mesmo tempo (o "database is locked" foi corrigido NA RAIZ nesta
  rodada — vale re-testar exatamente o cenário que falhava).
- [ ] Tradução Confiável §8.3 (seleção com rodapé; "Traduzir Página" sem loop).

## 6. Como reportar

Como em julho: prints + 1 linha do que esperava vs o que viu. Se travar, rode
`Diagnostico.bat` e mande o texto. Feedback pode ser por item deste roteiro
(ex.: "item 2.1 ok, item 2.2 ainda corta o rótulo X").
