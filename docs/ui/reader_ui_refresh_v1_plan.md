---
title: "Marco de Retorno e Recomendações — Reader UI Refresh / Design System Dark-First"
status: "Proposta para validação no Antigravity"
version: "1.0-proposta"
date: "2026-05-23"
audience: ["Engenharia", "Produto", "QA", "UX/UI", "Acessibilidade", "Segurança"]
owner: "Engenharia de Produção / Antigravity Agent"
related_report: "Relatório do Projeto v1.0 — Biblioteca Pessoal Inteligente"
rollback_marker: true
---

# Marco de Retorno e Recomendações — Reader UI Refresh / Design System Dark-First

> **Objetivo deste documento:** registrar, de forma completa e verificável, as recomendações para a revisão visual do aplicativo **Biblioteca Pessoal Inteligente**, tratando a proposta HTML/Tailwind como **protótipo visual**, não como implementação final. Este documento deve servir como **marco de retorno/rollback funcional e visual** caso as alterações finais de UI não gerem o resultado esperado.

---

## 0. Decisão executiva

```text
Decisão: APROVAR a proposta visual como direção de produto.
Status do HTML fornecido: PROTÓTIPO, NÃO IMPLEMENTAÇÃO.
Caminho recomendado: implementação nativa PyQt6/QSS, sem dependências remotas.
Impacto no fechamento da fase atual: não bloquear fechamento; registrar como backlog P2.
Marco de retorno: preservar estado atual validado antes da implementação visual.
```

A proposta visual é forte e coerente com um aplicativo de leitura moderno: dark-first, foco no conteúdo, sidebars limpas, RAG menos poluído e Audio Reader integrado à toolbar. Porém, por envolver interface de leitura, acessibilidade, offline-first, segurança e estabilidade, não deve ser aplicada diretamente como HTML runtime sem uma fase controlada.

---

## 1. Contexto

A fase atual consolidou:
- Audio Reader MVP funcional no Windows/SAPI5;
- correção do ciclo de vida do `pyttsx3`;
- limpeza de hifens de PDF;
- limpeza de referências inline no TTS;
- limitação conhecida em epígrafes/citações destacadas;
- relatório v1.0 em refinamento;
- backlog de segurança OPDS e UX do Audio Reader.

Foi proposta uma nova UI com os seguintes conceitos:
- Dark Mode First com Glassmorphism.
- Foco no conteúdo e redução de poluição visual.
- Integração visual do Audio Reader na toolbar.
- Painéis laterais modernos/flutuantes para Sumário e IA/RAG.
- RAG Panel priorizando chat e ocultando configurações avançadas.

---

## 2. Princípio orientador

O aplicativo é um leitor. Portanto, a UI deve obedecer à seguinte hierarquia:

```text
1. Legibilidade do livro
2. Conforto visual prolongado
3. Estabilidade e fluidez de navegação
4. Acessibilidade
5. Ferramentas de apoio: Sumário, RAG, Audio Reader, Anotações
6. Estética visual
```

A estética premium é desejável, mas nunca deve prejudicar leitura, acessibilidade, desempenho ou privacidade.

---

## 3. Decisão de arquitetura visual

### 3.1 Recomendação principal

Implementar a nova direção visual como PyQt6/QSS nativo, reaproveitando a arquitetura atual do projeto.

```text
HTML/Tailwind atual -> referência visual/protótipo
Implementação final -> PyQt6 Widgets + QSS + assets locais
```

### 3.2 Por que não implementar o HTML diretamente

O HTML fornecido usa:
```html
<script src="https://cdn.tailwindcss.com"></script>
<script src="https://unpkg.com/lucide@latest"></script>
@import url('https://fonts.googleapis.com/...')
```
Isso é incompatível com o objetivo local-first/offline-first do projeto final, pois introduz dependências remotas, risco de supply chain e falha offline.

### 3.3 Quando considerar QWebEngine

QWebEngine só deve ser considerado se houver uma decisão arquitetural formal, porque implicaria:
- runtime web embutido;
- bridge JS/Python via QWebChannel;
- empacotamento de assets;
- nova superfície de segurança;
- complexidade de testes;
- risco de regressão na integração PyQt6 existente.

Recomendação: não usar QWebEngine para a UI principal nesta etapa.

---

## 4. Marco de retorno obrigatório

Antes de qualquer alteração visual profunda, criar um marco explícito de retorno.

### 4.1 Nome sugerido

```text
tag: pre-reader-ui-refresh-v1
branch: feature/reader-ui-refresh-v1
checkpoint doc: docs/ui/reader_ui_refresh_v1_plan.md
```

### 4.2 Estado que deve ser preservado

O marco deve representar o estado atual validado:
- suíte completa verde;
- Audio Reader funcional;
- RAG funcional/degradável;
- OPDS implementado;
- relatório v1.0 ajustado;
- sem alterações visuais profundas aplicadas.

### 4.3 Comandos sugeridos para o usuário/Antigravity

> Executar apenas se o usuário aprovar. Não executar comandos destrutivos.

```bash
git status --short
git branch --show-current
git tag pre-reader-ui-refresh-v1
```

Se preferir branch:
```bash
git checkout -b feature/reader-ui-refresh-v1
```

### 4.4 Plano de rollback

Se o refresh visual não atingir os critérios de aceite:

```bash
git checkout main
git checkout -b rollback/reader-ui-refresh-v1-review
git revert <commits_do_refresh_visual>
```

Ou, se a mudança estiver isolada em branch:
```bash
git checkout main
git branch -D feature/reader-ui-refresh-v1
```

---

## 5. Avaliação da proposta visual

### 5.1 Pontos fortes

- Visual moderno e premium.
- Melhor foco no conteúdo.
- RAG Panel mais limpo.
- Audio Reader aparece no lugar correto: toolbar do leitor.
- Sumário e IA separados do conteúdo.
- Reconhece o backlog de epígrafes/citações.
- Usa hierarquia visual clara.

### 5.2 Pontos que exigem cuidado

- Dark mode não é automaticamente mais acessível.
- Glassmorphism pode reduzir contraste.
- Painéis laterais podem roubar área útil de leitura.
- HTML com CDN viola offline-first.
- WebEngine como runtime exigiria ADR.
- TTS visual precisa refletir estados reais do backend.
- O painel RAG não pode ocultar informações críticas de modelo/escopo/indexação.

---

## 6. Regras obrigatórias para implementação

### 6.1 Local-first/offline-first

O app final não pode depender de:
- CDN Tailwind;
- Google Fonts remoto;
- Lucide via unpkg;
- scripts remotos;
- imagens remotas;
- assets de terceiros não empacotados.

Todos os assets devem ser:
```text
locais
versionados
licenciados
empacotáveis
funcionais sem internet
```

### 6.2 Temas obrigatórios

Mesmo com dark-first, manter:
- Dark;
- Light;
- Sépia.

O usuário deve poder alternar tema. Dark mode não deve substituir os demais.

### 6.3 Acessibilidade

Critérios mínimos:
- contraste WCAG AA para texto normal;
- foco visível por teclado;
- navegação por Tab coerente;
- tooltips nos botões;
- nomes acessíveis em botões PyQt;
- não usar cor como único indicador de estado;
- ícones acompanhados de tooltip/label acessível;
- estados hover/focus/disabled distinguíveis.

### 6.4 Glassmorphism moderado

Permitido em:
- toolbar;
- painéis laterais;
- pequenos controles flutuantes;
- badges/status.

Evitar em:
- corpo do livro;
- parágrafos longos;
- caixas de leitura principal;
- inputs críticos se reduzir contraste;
- áreas com texto denso.

### 6.5 Responsividade desktop

Testar no mínimo:
- 1366x768;
- 1920x1080;
- 2560x1440, se possível;
- escala Windows 125%;
- telas pequenas com ambos os painéis ocultos.

### 6.6 Estado real do Audio Reader

O botão de áudio deve refletir estado real, não apenas animação local:

```text
Idle
Starting
Reading
Stopping
Stopped
Error
```

Critérios:
- Play inicia leitura real.
- Stop chama `AudioReaderService.stop()`.
- Replay após Stop funciona.
- Replay após fim natural funciona.
- Troca de página para áudio anterior.
- Fechamento do leitor encerra worker.

### 6.7 Estado real do RAG

O painel IA deve mostrar, de forma compacta:
- modelo atual;
- Ollama ativo/inativo;
- escopo atual: página/livro/biblioteca;
- status de indexação;
- fontes usadas na resposta;
- aviso quando resposta for local-only ou fallback.

### 6.8 OPDS e rede

A nova UI não deve ativar OPDS/web search implicitamente.
Qualquer recurso de rede deve ser:
- opt-in;
- visível;
- reversível;
- documentado.

---

## 7. Ajustes específicos no HTML protótipo

### 7.1 Tratar como protótipo

Adicionar cabeçalho se o HTML for salvo:
```html
<!--
PROTÓTIPO VISUAL — NÃO USAR EM PRODUÇÃO
Este arquivo usa CDNs e scripts remotos apenas para mock visual.
A implementação final deve ser PyQt6/QSS com assets locais.
-->
```

### 7.2 Remover dependências remotas na implementação final

Não usar no app final:
```html
<script src="https://cdn.tailwindcss.com"></script>
<script src="https://unpkg.com/lucide@latest"></script>
@import url('https://fonts.googleapis.com/...')
```

### 7.3 Corrigir classe inválida

Atual:
```html
class="w-80 ou 96 max-w-sm ..."
```

Corrigir no protótipo para uma forma válida:
```html
class="w-96 max-w-sm ..."
```
ou:
```html
class="w-80 max-w-sm ..."
```

### 7.4 Evitar posicionamento frágil

Atual:
```html
right-[380px]
```

Risco: quebra quando painel IA muda de largura ou é ocultado.
Recomendação:
- evitar posicionamento absoluto fixo;
- ancorar ao viewport do leitor;
- preferir toolbar ou overlay calculado.

### 7.5 Remover JS inline da implementação final

O JS inline é aceitável no protótipo, mas no app real o estado deve vir de signals/slots PyQt.

---

## 8. Design tokens recomendados

Criar tokens centrais em `styles.py` ou módulo equivalente.

```text
bg/base        # fundo principal
bg/surface     # painéis
bg/elevated    # cards/toolbars
bg/reader      # fundo da página do livro
fg/primary     # texto principal
fg/secondary   # texto secundário
fg/muted       # texto auxiliar
border/default
border/focus
accent/local   # verde esmeralda/local AI
accent/warning
accent/error
accent/info
selection/bg
highlight/bg
```

Paleta inicial sugerida
```text
Dark base:      #0f1115
Dark surface:   #161920
Dark elevated:  #20242d
Dark border:    #2d333f
Accent local:   #10b981
Accent hover:   #059669
Text primary:   #e5e7eb
Text secondary: #cbd5e1
Text muted:     #94a3b8
```

Regras
- Não usar preto puro para fundo principal.
- Não usar branco puro para corpo de texto longo.
- Cores de destaque devem ser desaturadas o suficiente para leitura.
- Estados de erro não podem depender apenas de vermelho.

---

## 9. Layout recomendado

### 9.1 Estrutura

```text
MainWindow
├── TopToolbar
│   ├── Toggle Sumário
│   ├── Navegação de página / zoom
│   ├── AudioReaderControls
│   └── Toggle IA / Tema / Anotações
│
├── ContentArea
│   ├── TocSidebar         ocultável/redimensionável
│   ├── ReaderCanvas       foco principal
│   └── RagSidebar         ocultável/redimensionável
│
└── OptionalStatusBar
    ├── estado RAG
    ├── estado TTS
    └── estado OPDS, se ativo
```

### 9.2 Sumário

- Deve ser ocultável.
- Deve ter destaque de capítulo atual.
- Deve preservar navegação existente.
- Não deve consumir espaço em telas pequenas.

### 9.3 ReaderCanvas

- Prioridade máxima.
- Largura confortável.
- Sem glassmorphism no texto longo.
- Tipografia adequada por formato.
- Tema sépia deve continuar excelente para leitura longa.

### 9.4 RAG Sidebar

- Chat como foco.
- Configurações avançadas em menu.
- Fontes/citações visíveis.
- Estado local claro.
- Não usar “Online” se estiver local; preferir “Local ativo”.

### 9.5 AudioReaderControls

MVP visual:
```text
Play/Stop + velocidade atual
```

Próximo incremento:
```text
Play/Stop
Rate
Voice
Volume
Progress
Error state
```

---

## 10. Backlog a incluir no relatório v1.0

Adicionar item:

```md
### P2-005 — Reader UI Refresh / Design System Dark-First

**Status:** Pendente  
**Tipo:** UI / UX / Acessibilidade  
**Prioridade:** P2 / Alta  

#### Contexto
O aspecto visual é central para um aplicativo de leitura. Foi proposta uma nova UI dark-first com painéis laterais modernos, foco no conteúdo, RAG Panel menos poluído e controles TTS integrados à toolbar.

#### Decisão
A proposta é aprovada como direção visual. O HTML/Tailwind fornecido é protótipo e não implementação final.

#### Não fazer
- Não usar CDNs externas no app final.
- Não substituir PyQt6 por QWebEngine sem ADR.
- Não remover temas claro e sépia.
- Não aplicar glassmorphism ao corpo do texto longo.
- Não esconder status crítico de RAG/TTS.
- Não ativar OPDS/web search implicitamente.

#### Critérios de aceite
- App funciona 100% offline.
- Tema dark passa contraste WCAG AA.
- Light e sépia continuam disponíveis.
- Reader mantém prioridade visual sobre ferramentas.
- RAG Panel pode ser ocultado/redimensionado.
- Audio Reader mantém Play/Stop/replay.
- Sem regressão na suíte completa.
- Smoke visual em resoluções comuns.
```

---

## 11. ADR recomendado

Criar apenas se a mudança for além de ajustes QSS simples.
ADR-008 sugerido:

```text
.agents/adr/ADR-008-reader-ui-refresh-design-system.md
```

Conteúdo mínimo:

```md
# ADR-008: Reader UI Refresh and Dark-First Design System

## Status
Proposed

## Context
O aplicativo é centrado na experiência de leitura. A UI atual é funcional, mas pode ser modernizada para reduzir poluição visual, melhorar foco no conteúdo e integrar RAG/Audio Reader de forma mais natural.

## Decision
A nova direção visual será implementada preferencialmente com PyQt6/QSS nativo e assets locais. O protótipo HTML/Tailwind será usado apenas como referência visual. QWebEngine não será adotado para a UI principal sem ADR específica.

## Consequences
- Preserva offline-first.
- Reduz risco de dependências remotas.
- Mantém integração nativa com workers e signals.
- Exige gate de acessibilidade e contraste.
- Glassmorphism deve ser usado com moderação.
```

---

## 12. Arquivos prováveis a alterar na próxima fase

```text
src/gui/styles.py
src/gui/reader_view.py
src/gui/widgets/rag_panel.py
src/gui/widgets/annotation_panel.py
src/gui/workers/audio_worker.py        # somente se novos sinais forem necessários
docs/project_report_v1.md
docs/ui/reader_ui_refresh_v1_plan.md
docs/prototypes/reader_ui_refresh_v1.html   # opcional, protótipo não-prod
.agents/adr/ADR-008-reader-ui-refresh-design-system.md  # se necessário
```

---

## 13. Testes e validações obrigatórias

### 13.1 Testes automatizados

```bash
python -m pytest tests/
```

Se houver testes GUI:
```bash
python -m pytest tests/ -q
python -m pytest tests/test_audio_reader_service.py -q
```

### 13.2 Checagens arquiteturais

```bash
grep -R "https://cdn\|unpkg\|fonts.googleapis" src/ docs/ || true
grep -R "QWebEngineView" src/gui || true
grep -R "PyQt6" src/core/audio src/core/rag || true
```

No Windows PowerShell:
```powershell
Select-String -Path src/**/*.py,docs/**/*.md -Pattern "https://cdn|unpkg|fonts.googleapis"
Select-String -Path src/gui/**/*.py -Pattern "QWebEngineView"
Select-String -Path src/core/audio/**/*.py,src/core/rag/**/*.py -Pattern "PyQt6"
```

### 13.3 Validação de contraste

Validar pelo menos:
```text
fg/primary sobre bg/reader
fg/secondary sobre bg/surface
accent/local sobre bg/elevated
botão Play em estados idle/reading/error
input do RAG
badges de fonte
links do sumário
highlight do usuário
```

Critério:
```text
Texto normal: >= 4.5:1
Texto grande/UI relevante: >= 3:1
Foco/contorno: visível sem depender só de cor
```

### 13.4 Smoke visual

Executar checklist manual:

```text
[ ] Abrir app.
[ ] Abrir biblioteca.
[ ] Abrir PDF.
[ ] Abrir EPUB.
[ ] Alternar tema Dark/Light/Sépia.
[ ] Abrir/fechar sumário.
[ ] Abrir/fechar painel IA.
[ ] Redimensionar janela.
[ ] Testar em 1366x768.
[ ] Testar com scaling 125%.
[ ] Acionar Audio Reader Play.
[ ] Acionar Stop.
[ ] Repetir Play após Stop.
[ ] Fazer pergunta no RAG Panel.
[ ] Confirmar fontes/citações visíveis.
[ ] Confirmar que app funciona sem internet.
```

### 13.5 Smoke de acessibilidade

```text
[ ] Navegação por Tab alcança botões principais.
[ ] Foco visual é claro.
[ ] Botões têm tooltip.
[ ] Ícones críticos têm accessibleName/accessibleDescription.
[ ] Não há informação transmitida apenas por cor.
[ ] Textos pequenos continuam legíveis.
[ ] Painéis podem ser ocultados sem perda de função principal.
```

---

## 14. Segurança e privacidade

### 14.1 Riscos introduzidos pela proposta

| ID | Risco | Severidade | Mitigação |
|---|---|---|---|
| UI-SEC-001 | CDN externa viola offline-first | Alta | Assets locais; QSS nativo. |
| UI-SEC-002 | QWebEngine amplia superfície de ataque | Média/Alta | Não usar sem ADR. |
| UI-SEC-003 | Web search/OPDS ativados por affordance visual | Alta | Nunca ativar implicitamente. |
| UI-SEC-004 | JS inline em protótipo confundido com produção | Média | Marcar como não-prod. |
| UI-SEC-005 | Fonts/assets de terceiros sem licença clara | Média | Empacotar e documentar licenças. |

### 14.2 Regras

- Sem rede remota para renderizar UI.
- Sem scripts remotos.
- Sem autoativação de OPDS.
- Sem autoativação de web search.
- Sem logging de conteúdo do livro em UI debug.

---

## 15. Revisão adversarial

### 15.1 Críticas ao design

- Dark mode first pode prejudicar leitura em ambientes claros.
- Glassmorphism pode parecer premium mas reduzir legibilidade.
- O painel de IA pode competir visualmente com o livro.
- Audio controls na toolbar podem poluir se crescerem demais.
- Verde esmeralda pode confundir “local ativo” com “online”.

### 15.2 Mitigações

- Manter temas alternativos.
- Usar glassmorphism apenas em chrome da aplicação.
- Tornar painéis ocultáveis/redimensionáveis.
- Usar labels precisos: “Local ativo”, “Ollama ativo”, “Offline”.
- Validar contraste e teclado antes de aceitar.

---

## 16. Critérios de aceite da fase visual

A fase Reader UI Refresh só deve ser aceita se:

```text
[ ] Nenhuma dependência remota adicionada.
[ ] Implementação feita em PyQt6/QSS ou ADR aprovada para alternativa.
[ ] Dark, Light e Sépia funcionam.
[ ] Contraste validado.
[ ] Reader continua foco central.
[ ] Sumário e IA são ocultáveis.
[ ] Audio Reader mantém fluxo validado.
[ ] RAG Panel mantém streaming/fallback/fontes.
[ ] App funciona sem internet.
[ ] Suíte completa passa.
[ ] Smoke visual passa.
[ ] Marco de retorno documentado.
```

---

## 17. Critérios de rejeição

Rejeitar a alteração visual se ocorrer qualquer item:

```text
[ ] App passa a depender de internet para renderizar UI.
[ ] Leitura longa fica menos legível.
[ ] Tema claro/sépia quebra ou desaparece.
[ ] Audio Reader perde Play/Stop/replay.
[ ] RAG Panel trava UI.
[ ] OPDS/web search são ativados sem ação explícita.
[ ] Contraste falha em texto principal.
[ ] Painéis impedem leitura em tela comum.
[ ] Suíte de testes falha sem justificativa.
[ ] Não há caminho claro de rollback.
```

---

## 18. Prompt completo para Antigravity

```text
MODO: PRODUCTION ENGINEERING

Tarefa: Registrar e validar proposta de Reader UI Refresh / Design System Dark-First como marco de próximo ciclo.

Contexto:
O projeto Biblioteca Pessoal Inteligente concluiu a fase atual com Audio Reader MVP validado, RAG local, OPDS e relatório v1.0. Foi proposta uma nova UI moderna baseada em dark mode first, glassmorphism, sidebars flutuantes, RAG Panel limpo e controles de Audio Reader na toolbar.

Objetivo:
Incluir a proposta visual como direção aprovada e backlog P2, criando um marco de retorno antes de qualquer implementação profunda.

Escopo:
- Adicionar backlog P2-005 ao relatório v1.0.
- Criar docs/ui/reader_ui_refresh_v1_plan.md com recomendações e critérios.
- Opcionalmente salvar o HTML como docs/prototypes/reader_ui_refresh_v1.html marcado como protótipo não-prod.
- Não alterar runtime do app nesta tarefa.

Fora de escopo:
- Não substituir ReaderView.
- Não adicionar Tailwind, Lucide, Google Fonts ou CDNs.
- Não usar QWebEngine sem ADR.
- Não alterar RAG, Audio Reader, OPDS, banco ou readers.
- Não executar comandos destrutivos.

Decisões obrigatórias:
1. O HTML é protótipo visual, não implementação.
2. Implementação recomendada é PyQt6/QSS nativo.
3. QWebEngine exige ADR separada.
4. App final deve funcionar 100% offline.
5. Dark-first não remove Light/Sépia.
6. Glassmorphism deve ser moderado.
7. O corpo do livro deve permanecer prioritário.
8. Audio Reader e RAG devem refletir estado real.

Validações:
- Confirmar que nenhuma dependência remota foi adicionada.
- Confirmar que nenhum arquivo runtime foi alterado.
- Confirmar que relatório v1.0 recebeu backlog P2-005.
- Confirmar que o documento de plano foi criado.

Critérios de aceite:
- docs/ui/reader_ui_refresh_v1_plan.md criado.
- project_report.md atualizado com P2-005.
- protótipo, se salvo, marcado como não-prod.
- nenhuma dependência externa adicionada.
- nenhuma alteração em código runtime.
- marco de retorno recomendado/documentado.

Relatório final:
- Arquivos alterados.
- Confirmação de não alteração runtime.
- Backlog adicionado.
- Decisões registradas.
- Riscos e próximos passos.
```

---

## 19. Recomendações finais

### Recomendação principal

Fechar a fase atual como validada e registrar a proposta visual como próximo ciclo P2.

### Ordem recomendada

```text
1. Ajustar relatório v1.0.
2. Criar marco/tag de retorno.
3. Registrar Reader UI Refresh P2-005.
4. Salvar protótipo como não-prod.
5. Planejar implementação PyQt6/QSS.
6. Só então iniciar alterações visuais.
```

### Não fazer agora

- Não aplicar o HTML diretamente.
- Não adicionar CDNs.
- Não reabrir Audio Reader MVP.
- Não trocar arquitetura de GUI.
- Não misturar refresh visual com OPDS Security.

---

## 20. Definição de pronto deste documento

Este documento estará pronto quando:

```text
[ ] For salvo em docs/ui/reader_ui_refresh_v1_plan.md ou equivalente.
[ ] O relatório v1.0 referenciar P2-005.
[ ] O usuário aprovar o marco de retorno.
[ ] O Antigravity confirmar que nenhuma alteração runtime foi feita.
[ ] O protótipo HTML, se salvo, estiver marcado como não-prod.
```
