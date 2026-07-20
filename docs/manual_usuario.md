# Manual do Usuário — Biblioteca Pessoal

Bem-vindo! A **Biblioteca Pessoal** é um aplicativo para Windows que organiza
seus livros digitais e ajuda você a ler mais e melhor: leitor para vários
formatos, anotações e destaques, narração em voz alta, tradução de páginas e
um assistente de inteligência artificial que responde perguntas sobre os seus
próprios livros — tudo funcionando **no seu computador**, sem enviar nada para
a internet.

> 💡 **Dica que vale por todo o manual:** este manual também está dentro do
> aplicativo, como o primeiro livro da sua biblioteca. Sempre que tiver uma
> dúvida, abra o **Assistente IA** (`Ctrl+R`) e pergunte com suas palavras —
> por exemplo, *"como importo meus livros?"* — que ele responde citando as
> páginas deste manual.

---

## 1. Instalação

O aplicativo é **portátil**: não precisa instalar nada.

1. Extraia o arquivo ZIP para qualquer pasta do seu computador (por exemplo,
   `Documentos` ou a Área de Trabalho). Evite pastas que exijam permissão de
   administrador, como `C:\Arquivos de Programas`.
2. Abra a pasta extraída e dê **dois cliques em "Biblioteca Pessoal"**.
3. Pronto. Na primeira vez, a abertura pode demorar um pouco mais (o Windows
   está lendo os arquivos pela primeira vez) — das próximas vezes será rápida.

**Requisitos:** Windows 10 ou 11 (64 bits), 8 GB de memória RAM (16 GB
recomendado para usar todos os recursos de IA) e espaço em disco: ~6 GB para o
aplicativo, ou ~15 GB se você instalar o assistente de IA completo. Placa de
vídeo é opcional — o app se adapta sozinho ao seu computador.

**Aviso do Windows:** ao abrir pela primeira vez, o Windows pode mostrar um
aviso de "aplicativo não reconhecido" (SmartScreen). Isso acontece com
qualquer programa novo sem assinatura digital. Clique em **"Mais informações"
→ "Executar assim mesmo"**.

**Seus dados** (livros importados, anotações, progresso) ficam na pasta
`data`, dentro da própria pasta do aplicativo. Para fazer backup, basta copiar
essa pasta.

---

## 2. Primeiro uso

Na primeira abertura, você vai encontrar este manual já na estante, como
primeiro livro — a biblioteca nunca começa vazia.

O aplicativo funciona por camadas: **tudo de leitura funciona imediatamente**,
e os recursos de IA são ativados quando você quiser:

| Recurso | Precisa de algo? |
|---|---|
| Importar, ler, anotar, buscar, estatísticas | Nada — funciona de cara |
| Ouvir livros (narração) | Nada — a voz já vem incluída |
| Livros escaneados (OCR) | Nada — automático |
| Traduzir páginas | 1 download automático na primeira vez (~2,4 GB) |
| Assistente de IA | Instalação guiada com 1 clique (ver seção 8) |

Quando um recurso precisar baixar algo, o próprio aplicativo pede sua
confirmação e mostra uma barra de progresso. Você nunca precisa abrir
terminal, digitar comandos ou instalar nada por fora.

---

## 3. Importando seus livros

Há três jeitos:

- **Arrastar e soltar**: arraste arquivos (ou uma pasta) para a janela do app.
- **Menu de importação** (`Ctrl+I`): clique em **Selecionar Arquivos** ou
  **Selecionar Pasta**. O diálogo mostra o progresso e avisa se algum livro
  **"Já existe na biblioteca (duplicata)"**.
- **Diretórios Monitorados**: em **⚙️ Configurações → 📚 Biblioteca**, adicione
  uma pasta do seu computador; tudo que você colocar nela aparece na
  biblioteca automaticamente.

**Formatos aceitos:** PDF, EPUB, MOBI, AZW/AZW3 (Kindle), DOCX (Word), TXT,
Markdown, FB2 e quadrinhos CBZ/CBR.

Na importação o app extrai capa, título e autor automaticamente e detecta
duplicatas (dá para desligar isso nas configurações).

---

## 4. Navegando pela biblioteca

A **barra lateral** à esquerda (`Ctrl+B` mostra/oculta) organiza tudo:

- **Todos os Livros**, **Lendo**, **Não Lidos**, **Lidos**, **Favoritos** —
  seções automáticas conforme seu progresso;
- **COLEÇÕES** — crie grupos seus (ex.: "Estudos", "Férias") com **Nova
  Coleção** e adicione livros pelo menu do botão direito sobre a capa;
- **Estatísticas** — painel completo de leitura (seção 10).

No topo da estante você alterna entre **▦ Grade** e **☰ Lista** e ordena por
**Data de adição**, **Última atividade**, **Título**, **Autor** ou
**Avaliação**. O clique com o **botão direito** sobre um livro abre atalhos:
favoritar, avaliar com estrelas, mover para coleção, alterar status, remover.

A **Pesquisa Global** (barra no topo) busca em duas camadas: nos
títulos/autores **e dentro do texto dos livros** — resultados de conteúdo
mostram o trecho encontrado e levam direto à página. Funciona até com começo
de palavra ("filos" encontra "filosofia").

---

## 5. Lendo um livro

Dê dois cliques na capa. Na barra do leitor você encontra:

- **← Biblioteca** — volta para a estante (o progresso é salvo sozinho);
- Navegação: **→ / Espaço / Page Down** avança; **← / Shift+Espaço / Page Up**
  volta; o indicador mostra a página atual e o total;
- **Zoom** (`Ctrl++` / `Ctrl+-`) e **Tipografia do leitor** (fonte, tamanho,
  espaçamento, tema da página);
- **📖 Página Dupla** (em "Mais opções ⋯") — duas páginas lado a lado;
- **Tela cheia** (`F11`);
- **Painel Sumário/Marcadores** — capítulos do livro e páginas marcadas;
- **Marcar página** (`Ctrl+D`) — cria um marcador na página atual;
- **Buscar no documento** (`Ctrl+F`) — busca só dentro do livro aberto.

**Livros escaneados:** se o PDF for uma digitalização (imagem, sem texto), o
app reconhece o texto automaticamente (OCR) para busca, narração e IA — sem
nenhuma configuração.

---

## 6. Anotações, destaques e marcadores

- **🖍️ Modo Marca-Texto** (em "Mais opções ⋯"): passe o mouse sobre o texto
  para destacar, como um marca-texto de verdade.
- **Selecionar texto** abre uma barrinha de ações rápidas: **Destacar**,
  **Anotar**, **Explicar** (a IA explica o trecho), **Traduzir**,
  **Flashcard**, **Definição rápida** e busca na **Web**.
- **Painel de Anotações**: lista tudo do livro atual em ordem de página;
  clique para ir até a página; renomeie ou apague o que quiser.
- Notas criadas pelo Assistente IA aparecem com o ícone 🤖 ("Nota da IA").
- **Exportar**: pelo menu do livro dá para exportar todas as anotações em um
  arquivo de texto organizado (Markdown), ótimo para revisão.

---

## 7. Ouvindo seus livros (narração)

Clique no botão **Ouvir** na barra do leitor:

- **🔊 Ouvir original** — narra o texto no idioma do livro (português e inglês
  são detectados automaticamente, cada um com voz adequada);
- **🌐 Ouvir traduzido (PT)** — traduz e narra em português;
- **🔁 Leitura Contínua** — o app vira as páginas sozinho enquanto narra;
- **🌐🔁 Leitura Contínua Traduzida (PT)** — as duas coisas juntas;
- **⏹️ Parar** interrompe; pausar retoma do mesmo ponto;
- **⚙️ Configurar vozes…** — escolha de vozes e velocidade (também em
  **Configurações → 🔊 Narração**).

A voz principal (Kokoro) **já vem incluída** e funciona sem internet. Na
primeira narração de cada sessão o motor de voz demora alguns segundos para
"acordar" (em computadores mais antigos, até um minuto) — depois flui.
Se o seu computador for modesto, o app troca sozinho para um motor mais leve.

---

## 8. Assistente de IA — perguntas sobre os seus livros

O assistente responde perguntas usando **os livros da sua estante** como
fonte, com citações das páginas. Tudo roda no seu computador: suas perguntas
e seus livros **não saem da sua máquina**.

**Ativando (uma vez só):** abra o Assistente (`Ctrl+R`). Se a IA ainda não
estiver instalada, aparece a tela **"Assistente de Biblioteca —
Configuração"**: clique em **Instalar Ollama Automaticamente** e aguarde a
barra de progresso (≈700 MB + modelos escolhidos conforme a memória do seu
computador). Você também pode **Continuar sem o Assistente de IA** — todo o
resto do app segue funcionando.

**Usando:**
- Digite na caixa **"Pergunte sobre seus livros…"** e pressione Enter. Com um
  livro aberto, a pergunta considera o livro atual; na biblioteca, considera
  toda a estante.
- A resposta traz **📖 Fontes Consultadas** e citações clicáveis no texto —
  clique para saltar à página exata do livro.
- Botões úteis na resposta: **Salvar como Anotação** (vira nota no livro),
  **Criar Flashcard** (vira cartão de estudo), **Útil / Não ajudou**
  (seu feedback ensina o assistente a melhorar).
- **Estudar a página**: no leitor, gera um resumo de estudo da página atual.
- **🧠 Agente Proativo**: se quiser, o app observa sua leitura e oferece
  insights sozinho — intensidade **Desligado / Leve / Moderado / Estudo**
  (padrão: desligado; ative no leitor).

**Sobre o tempo de resposta:** a IA local "pensa" antes de escrever. Perguntas
completas sobre um livro podem levar **alguns minutos**, principalmente a
primeira do dia. Isso é normal — o indicador 💭 mostra que ela está
trabalhando; o botão **Parar** cancela quando quiser.

**Indexação:** para responder sobre um livro, o app precisa "estudá-lo" antes
(indexar). Isso acontece sozinho, aos poucos, quando o computador está
ocioso. Livros recém-importados podem demorar um pouco até entrarem nas
respostas — a barra lateral do assistente mostra o andamento em
**📚 Indexação**.

---

## 9. Tradução de páginas

No leitor, **🌐 Traduzir Página (texto)** mostra a página em português.

- Na **primeira tradução**, o app baixa o tradutor offline (~2,4 GB) com sua
  confirmação e barra de progresso. Depois disso, funciona **sem internet**.
- Páginas já traduzidas ficam guardadas: ao reler, a tradução aparece na hora.
- Em **Configurações → ⚙️ Avançado** há a opção **"Revisar tradução com LLM
  local"**: quando o Assistente de IA está instalado, ele revisa e melhora o
  texto traduzido.

---

## 10. Flashcards e estatísticas

**Flashcards** (`Ctrl+Shift+F`): cartões de pergunta-e-resposta para memorizar
o que você lê. Crie a partir das respostas do assistente (**Criar
Flashcard**), de anotações, ou manualmente. A revisão usa repetição espaçada:
o app mostra cada cartão na hora certa para a memória fixar.

**Estatísticas** (barra lateral → **Estatísticas**): total de livros, lendo
agora, lidos, favoritos, **tempo de leitura**, **sequência** de dias lendo
(streak), **minutos de leitura das últimas 8 semanas** e **📚 Meta do ano** —
defina sua meta anual de livros em **Configurações → 📚 Biblioteca**. O
cronômetro conta apenas leitura de verdade (pausa quando você minimiza a
janela — a menos que esteja ouvindo a narração).

---

## 11. Configurações

`Ctrl+,` abre **⚙️ Configurações**, com cinco abas:

- **🎨 Aparência** — tema **🌙 Escuro**, **☀️ Claro** ou **📜 Sépia**;
- **📖 Leitor** — fonte, tamanho, espaçamento e margens padrão;
- **📚 Biblioteca** — modo de visualização, ordenação, opções de importação,
  **Diretórios Monitorados** e **Meta anual de livros lidos**;
- **🔊 Narração** — voz do narrador e do assistente, velocidade, estilo e
  **fallback automático para engine mais leve**;
- **⚙️ Avançado** — auto-indexação da IA, grafo de conceitos, revisão de
  tradução. Se não tiver certeza, deixe como está: os padrões se ajustam ao
  seu computador.

**Restaurar Padrões** desfaz qualquer ajuste.

---

## 12. Atalhos de teclado

Pressione `F1` a qualquer momento para ver esta lista dentro do app
(**⌨️ Atalhos de Teclado**):

| Onde | Atalho | Ação |
|---|---|---|
| Geral | F1 | Abrir a janela de atalhos |
| Leitor | → / Espaço / Page Down | Próxima página |
| Leitor | ← / Shift+Espaço / Page Up | Página anterior |
| Leitor | Esc | Fechar o leitor / cancelar ação atual |
| Leitor | Ctrl++ / Ctrl+- | Aumentar / diminuir zoom |
| Leitor | Ctrl+F | Buscar no documento |
| Leitor | Ctrl+D | Marcar/desmarcar a página atual |
| Leitor | F11 | Alternar tela cheia |
| Biblioteca | Ctrl+I | Importar (diálogo completo) |
| Biblioteca | Ctrl+O | Importar arquivo rápido |
| Biblioteca | Ctrl+Shift+O | Importar pasta |
| Geral | Ctrl+, | Abrir Configurações |
| Geral | Ctrl+Shift+A | Abrir o Assistente de Livros (IA) |
| Geral | Ctrl+Shift+F | Abrir Flashcards |
| Geral | Ctrl+B | Mostrar/ocultar a barra lateral |
| Geral | Ctrl+R | Mostrar/ocultar o Assistente IA |
| Geral | Ctrl+Q | Sair do aplicativo |

---

## 13. Recursos para usuários avançados (opcional)

Pode pular esta seção com segurança — nada aqui é necessário no dia a dia.

- **Servidor OPDS** (barra lateral → **Iniciar Servidor OPDS**): compartilha
  sua biblioteca na rede local para apps de leitura no celular/tablet que
  falem o padrão OPDS.
- **Servidor MCP**: permite que assistentes de IA no seu computador (Claude
  Desktop/Code, Cursor, Windsurf, VS Code com Copilot, Cline, Zed, Gemini
  CLI, LM Studio e outros hosts MCP locais) consultem sua biblioteca. Tudo em
  **⚙️ Configurações → 🔌 Integrações**: lá estão o comando pronto para
  copiar (Claude Code), o bloco de configuração para os demais programas e a
  chave **"Permitir que assistentes escrevam na biblioteca"** — desligada por
  padrão. Leitura é sempre permitida; a escrita, quando ligada, é aditiva
  (assistentes nunca apagam nem editam o que já existe).

---

## 14. Solução de problemas

**O app demora para abrir na primeira vez.** Normal — o Windows está lendo os
arquivos do app pela primeira vez. Da segunda em diante é bem mais rápido.

**O Windows bloqueou a abertura (SmartScreen/antivírus).** Clique em "Mais
informações" → "Executar assim mesmo". O app não tem assinatura digital nesta
versão de testes, por isso o aviso.

**"Ollama não detectado" ao abrir o Assistente.** A IA local não está
instalada ou não está rodando. Clique em **Instalar Ollama Automaticamente**
na tela de configuração que aparece. Se já instalou, reinicie o computador e
tente de novo.

**A resposta da IA está demorando muito.** Alguns minutos é o esperado — a IA
local raciocina antes de escrever (indicador 💭). Se quiser respostas mais
rápidas, use um modelo menor em **⚙️ Modelo de IA** na barra lateral do
assistente.

**A primeira narração/tradução demora.** O motor correspondente está sendo
carregado (ou baixado, no caso da tradução). As próximas vezes são rápidas.

**Um livro não aparece nas respostas da IA.** Ele ainda não foi indexado.
Deixe o computador ocioso alguns minutos com o app aberto, ou clique em
**Reindexar Biblioteca** na barra lateral do assistente.

**Um PDF escaneado não tem busca/narração.** O reconhecimento (OCR) roda
conforme a necessidade e pode levar alguns minutos num livro grande. Abra o
livro e aguarde; as páginas processadas passam a funcionar.

**Quero levar meus dados para outro computador.** Copie a pasta inteira do
aplicativo (ela contém a pasta `data` com tudo seu).

---

## 15. Reportando um problema (versão de testes)

Você está usando uma versão de testes — seu feedback é o objetivo! Ao relatar
um problema, ajude dizendo:

1. **O que você fez** (passo a passo, ex.: "importei um PDF e cliquei em
   Ouvir");
2. **O que aconteceu** e **o que você esperava**;
3. Se apareceu mensagem de erro, uma **foto/print da tela**;
4. Como é seu computador (Windows 10 ou 11, quanto de memória, se tem placa
   de vídeo — se souber).

Envie para o contato indicado no arquivo `LEIA-ME.txt` da pasta do app.

---

## 16. Privacidade

Tudo funciona no seu computador: livros, anotações, perguntas à IA, traduções
e áudio **não são enviados para a internet**. Os únicos downloads são os que
você autoriza (motor de tradução e assistente de IA), vindos de fontes
oficiais. Não há coleta de dados, conta, cadastro nem anúncios.

*Boa leitura! 📚*
