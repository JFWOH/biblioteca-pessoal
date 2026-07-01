---
title: "Contrato de Execução — Fase 11: Agente Proativo de Leitura (MVP)"
status: "Aprovada para execução autônoma"
version: "1.0-aprovada"
date: "2026-05-30"
audience:
Engenharia
Produto
QA
Segurança
Antigravity Agent
owner: "Engenharia de Produção / Antigravity Agent"
phase: "11"
execution_mode: "autonomous"
requires_manual_confirmation: false
related_docs:
"docs/agents/proactive_reading_agent_mvp.md"
"project_report.md"
rollback_marker: true
---
Contrato de Execução — Fase 11: Agente Proativo de Leitura (MVP)
> **Objetivo deste documento:** registrar de forma explícita as decisões humanas já aprovadas para a **Fase 11 — Agente Proativo de Leitura (MVP)**, permitindo **execução autônoma** pelo Antigravity **sem novas confirmações manuais**, desde que o agente respeite integralmente o escopo, os limites e os critérios definidos aqui.
---
0. Decisão executiva
```text
Decisão: APROVAR execução autônoma da Fase 11.
Modo: Execução sem confirmações humanas adicionais durante a fase.
Condição: O agente deve obedecer integralmente este contrato e o documento técnico do MVP.
Documento técnico de referência: docs/agents/proactive_reading_agent_mvp.md
Regra central: Se surgir conflito entre implementação desejável e contrato aprovado, o contrato prevalece.
```
---
1. Escopo aprovado
A Fase 11 deve implementar um MVP funcional do Agente Proativo de Leitura com as seguintes capacidades:
1.1 Comportamento do recurso
gerar observações assistivas curtas a partir da página/trecho atual;
operar como camada opcional do reader;
manter o corpo do livro como foco principal;
evitar intrusão visual e cognitiva;
não substituir o fluxo principal de leitura.
1.2 UX mínima obrigatória
toggle ligar/desligar do recurso;
intensidade configurável:
desligado
leve
moderado
estudo
exibição discreta no reader;
identificação clara de que a observação é do sistema;
caminho visual para ignorar ou ocultar observações.
1.3 Confiabilidade mínima obrigatória
Toda observação deve ser:
grounded no trecho/página atual;
curta;
sem spoiler;
rotulada por tipo e confiança;
coerente com o modo local-first do projeto.
1.4 Integração de modelos
Gemma 4 E4B como padrão do MVP;
Gemma 4 12B como modo avançado quando suportado por hardware;
fallback e degradação graciosa obrigatórios.
---
2. Fora de escopo aprovado
O agente não deve implementar nesta fase:
redesign amplo do reader por causa da feature;
comentários longos em todas as páginas;
qualquer forma de comentário contínuo/invasivo;
ativação implícita de internet, web search ou serviços remotos;
autonomia para criar spoilers ou observações preditivas da trama;
integração multimodal avançada completa (diagramas/tabelas/imagens complexas);
reabertura da UX de scans;
substituição do chat principal do agente;
reestruturação do pipeline principal de RAG;
mudanças em OCR, tradução offline, Audio Reader ou Sidebars além do necessário para não regressão.
---
3. Fonte de verdade da fase
A implementação deve obedecer, nesta ordem:
Este contrato de execução
`docs/agents/proactive_reading_agent_mvp.md`
`AGENTS.md`
`.agents/rules/governance.md`
`project_report.md`
Regra de precedência
Se houver tensão entre:
a governança genérica do projeto, e
a execução autônoma aprovada para a Fase 11,
o Antigravity deve tratar este contrato como override escopado da fase.
---
4. Decisões humanas já aprovadas (não perguntar novamente)
O Antigravity não precisa pedir confirmação sobre os itens abaixo:
4.1 Default do recurso
o Agente Proativo de Leitura deve ficar desligado por padrão.
4.2 Intensidade inicial recomendada
quando habilitado pela primeira vez, o modo sugerido ao usuário deve ser Leve.
4.3 Comportamento visual preferido
preferir rodapé colapsado a badge invasivo;
a observação deve ficar visualmente separada do corpo do livro.
4.4 Modelo padrão
usar Gemma 4 E4B como padrão do MVP.
4.5 Modelo avançado
usar Gemma 4 12B apenas quando:
estiver disponível;
o hardware suportar;
o modo avançado for permitido pela política da feature.
4.6 Política de hardware
capability detection é obrigatória;
não assumir suporte ao 12B por padrão;
se houver dúvida de capacidade, priorizar E4B.
4.7 Regra anti-spoiler
nenhuma observação pode antecipar fatos futuros da obra.
4.8 Regra de frequência
o sistema deve ser conservador;
melhor não mostrar observação do que mostrar observação fraca/intrusiva.
4.9 Modo de operação
100% local-first;
sem dependência remota obrigatória.
---
5. Limites de autonomia do Antigravity
O Antigravity pode decidir autonomamente:
a melhor implementação interna de arquitetura dentro do escopo aprovado;
quais arquivos modificar para atingir o objetivo;
a melhor forma de estruturar testes e fallback;
a melhor lógica de capability detection;
a melhor heurística de triggering inicial;
a melhor forma de exibir labels e confiança, desde que respeite a UX aprovada.
O Antigravity não pode decidir autonomamente:
mudar o default do recurso para ligado por padrão;
remover o caráter opcional da feature;
usar 12B como padrão universal;
introduzir rede/remoto;
expandir a fase para multimodal avançado completo;
criar comentários longos ou invasivos na leitura;
introduzir nova dependência arquitetural grande sem necessidade real.
---
6. Política obrigatória de confiabilidade
6.1 Toda observação deve indicar
Tipo:
Observação do texto
Contexto externo
Hipótese interpretativa
Confiança:
Alta
Média
Baixa
6.2 Toda observação deve obedecer
grounding local no trecho/página atual;
comprimento curto;
ausência de spoiler;
ausência de tom autoritativo;
clareza de que se trata de observação do sistema.
6.3 Política de tamanho
observação padrão: 1–4 frases.
6.4 Política de frequência
Implementar política conservadora equivalente a:
```text
Leve:      no máximo 1 observação por página/spread
Moderado:  no máximo 1 observação por página, apenas com gatilho forte
Estudo:    no máximo 1 por página + 1 sugestão eventual por capítulo
```
---
7. Política obrigatória de hardware e fallback
7.1 Capability detection obrigatória
Antes de usar o tier avançado, verificar:
disponibilidade do modelo local;
memória disponível;
latência;
estado de carga do sistema;
impacto na experiência do reader.
7.2 Hierarquia de fallback aprovada
```text
Tier A → Gemma 4 12B
Tier B → Gemma 4 E4B
Tier C → heurística local / supressão segura
```
7.3 Regra de degradação graciosa
Se o sistema não puder oferecer a melhor qualidade, ele deve:
degradar para uma capacidade inferior útil;
ou suprimir a observação;
mas nunca degradar a UX principal do leitor.
---
8. Arquivos que podem ser criados ou alterados
O Antigravity pode criar/alterar arquivos necessários dentro do escopo da fase, incluindo, se necessário:
```text
src/core/proactive_reader_service.py            [NOVO]
src/core/proactive_trigger_engine.py            [NOVO]
src/core/hardware_capability_service.py         [NOVO ou extensão]
src/gui/reader_view.py
src/gui/main_window.py
src/gui/styles.py
data/config.json
tests/test_proactive_reader_service.py          [NOVO]
tests/test_proactive_trigger_engine.py          [NOVO]
tests/test_reader_proactive_integration.py      [NOVO]
docs/agents/proactive_reading_agent_mvp.md      [referência]
```
Regra de contenção
Não criar arquivos adicionais desnecessários.  
Criar apenas o que:
acelera a implementação;
melhora a segurança da fase;
sustenta testes e manutenção;
evita ambiguidade operacional.
---
9. Testes obrigatórios da fase
O Antigravity deve concluir a fase com testes que cubram no mínimo:
9.1 Funcionais
ativar/desativar o recurso;
observação aparece quando há gatilho;
observação não aparece sem gatilho forte;
intensidade altera comportamento.
9.2 Confiabilidade
rotulagem correta;
ausência de spoiler;
observação curta e útil.
9.3 Hardware / fallback
com 12B disponível → modo avançado usa 12B;
sem 12B → usa E4B;
com hardware degradado → heurística ou supressão.
9.4 Regressão
reader continua estável;
viewport/navegação continuam estáveis;
OCR, tradução offline, RAG e Audio Reader continuam sem regressão.
---
10. Critérios de conclusão da fase
A Fase 11 só pode ser considerada pronta quando:
```text
[ ] O recurso é opcional e pode ser desligado.
[ ] O default continua desligado.
[ ] As observações são discretas, curtas e úteis.
[ ] Toda observação vem rotulada por tipo/confiança.
[ ] Não há spoiler.
[ ] O fallback E4B ↔ 12B funciona.
[ ] Hardware incompatível não degrada a UX principal.
[ ] O app continua local-first.
[ ] Há testes cobrindo comportamento e fallback.
[ ] Há plano de rollback claro.
```
---
11. Rollback obrigatório
Se a implementação falhar em qualquer um dos critérios de aceite ou introduzir regressão relevante:
reverter para o estado imediatamente anterior à Fase 11;
preservar o comportamento atual do reader sem a feature;
desabilitar a feature por padrão até correção.
Regra prática
Melhor remover/desligar a feature do que deixar o reader pior.
---
12. Resultado esperado da execução autônoma
Ao final da execução autônoma, o Antigravity deve entregar:
descoberta consolidada;
patch em diff unificado;
arquivos alterados;
testes criados/alterados;
relatório de segurança;
revisão adversarial;
instruções de execução;
plano de rollback;
checklist final da fase.
Sem pedir confirmações adicionais ao usuário durante a fase.
---
13. Definição de pronto deste contrato
Este contrato estará pronto quando:
```text
[ ] For salvo como docs/agents/phase_11_execution_contract.md
[ ] Estiver referenciado no prompt da Fase 11
[ ] O Antigravity puder executar a fase sem novas confirmações humanas
[ ] O documento técnico do MVP continuar acessível como referência principal
```