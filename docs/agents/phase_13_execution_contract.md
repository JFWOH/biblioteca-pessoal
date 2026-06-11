---
title: "Contrato de Execução — Fase 13: Audio Reader 2.0 / Narração Expressiva"
status: "Aprovada para execução autônoma (corrigida e atualizada)"
version: "1.1-final"
date: "2026-05-30"
audience:
Engenharia
Produto
QA
Acessibilidade
Segurança
Antigravity Agent
owner: "Engenharia de Produção / Antigravity Agent"
phase: "13"
execution_mode: "autonomous"
requires_manual_confirmation: false
related_docs:
"docs/agents/phase_13_audio_reader_2_0_mvp.md"
"project_report.md"
rollback_marker: true
mode: "PRODUCTION ENGINEERING"
---
Contrato de Execução — Fase 13: Audio Reader 2.0 / Narração Expressiva
> **Objetivo deste documento:** registrar de forma explícita as decisões humanas já aprovadas para a **Fase 13 — Audio Reader 2.0 / Narração Expressiva**, permitindo **execução autônoma** pelo Antigravity **sem novas confirmações manuais**, desde que a implementação respeite integralmente este contrato, o documento técnico da fase e as regras gerais do projeto.
>
> **Importante:** esta é a versão **corrigida e atualizada** do contrato. Ela preserva a intenção original da Fase 13, mas já incorpora o estado atual da implementação: **Kokoro** como backend principal do MVP, **Piper** como fallback leve, e a abertura da **Fase 13A — Otimização do Pipeline de Narração** como subfase corretiva obrigatória.
---
0. Decisão executiva
```text
Decisão: APROVAR execução autônoma da Fase 13.
Modo: Execução sem confirmações humanas adicionais durante a fase.
Condição: O agente deve obedecer integralmente este contrato e o documento técnico da Fase 13.
Documento técnico de referência: docs/agents/phase_13_audio_reader_2_0_mvp.md
Regra central: se surgir conflito entre uma escolha de implementação e este contrato, o contrato prevalece.
```
---
1. Escopo aprovado
A Fase 13 deve implementar um MVP funcional de melhoria de narração para o aplicativo, com as seguintes capacidades:
1.1. Comportamento do recurso
elevar perceptivelmente a qualidade da leitura falada;
separar conceitualmente e, quando possível, tecnicamente:
Narrador do livro
Voz do assistente
manter a experiência local-first;
preservar fluidez do reader;
não transformar a fase em projeto de áudio multimodal avançado.
1.2. Capacidades mínimas obrigatórias
camada de abstração de TTS local;
suporte a múltiplos backends ou, no mínimo, arquitetura preparada para isso;
pré-processamento de texto para fala;
fallback por hardware/capacidade;
degradação graciosa;
controles mínimos de voz/configuração;
pipeline de reprodução suficientemente contínuo para leitura prolongada.
1.3. Trilha técnica aprovada
O MVP pode incluir, no mínimo, suporte arquitetural para:
Piper
Kokoro
Qwen3-TTS (trilha avançada opcional)
Sherpa-ONNX (runtime/infraestrutura quando fizer sentido)
---
2. Fora de escopo aprovado
O agente não deve implementar nesta fase:
clonagem de voz personalizada;
voice design avançado como requisito central do MVP;
multi-speaker dramático;
leitura dramatizada longa tipo podcast/audiobook premium;
dependência obrigatória de GPU;
dependência obrigatória de nuvem;
redesign amplo do reader;
sync de preferências multi-dispositivo;
VibeVoice como engine principal do MVP;
ampliação do escopo para ASR/voice assistant completo.
---
3. Fonte de verdade da fase
A implementação deve obedecer, nesta ordem:
Este contrato de execução
`docs/agents/phase_13_audio_reader_2_0_mvp.md`
`AGENTS.md`
`.agents/rules/governance.md`
`project_report.md`
Regra de precedência
Se houver tensão entre:
a governança genérica do projeto; e
a execução autônoma aprovada para a Fase 13,
o Antigravity deve tratar este contrato como override escopado da fase, sem revogar as regras globais de segurança, testes, arquitetura e reporting.
---
4. Decisões humanas já aprovadas (não perguntar novamente)
O Antigravity não precisa pedir confirmação sobre os itens abaixo:
4.1. Backend padrão do MVP
Kokoro deve ser tratado como backend padrão de qualidade do MVP.
4.2. Backend de fallback leve
Piper deve ser tratado como fallback leve e rápido.
4.3. Backend avançado opcional
Qwen3-TTS pode ser incluído como trilha avançada opcional, mas não como dependência básica do MVP.
4.4. Papel do Sherpa-ONNX
Sherpa-ONNX pode ser usado como camada de runtime/infraestrutura, empacotamento ou alternativa de integração local, quando fizer sentido técnico.
4.5. Papel do VibeVoice
VibeVoice não deve ser usado como engine principal nesta fase.
No máximo, pode ser citado como trilha futura/experimental fora do MVP.
4.6. Perfil padrão do livro
o perfil padrão do narrador do livro deve ser sereno.
4.7. Voz do assistente
a voz do assistente deve usar preferencialmente a mesma engine do livro, mas com perfil/voz diferente quando possível.
4.8. Princípio local-first
nenhuma dependência remota obrigatória deve ser introduzida.
4.9. Regra de performance
melhor degradar para um backend mais leve do que travar a UI.
4.10. Pré-processamento de texto
a fase deve obrigatoriamente incluir melhoria ou criação de camada de pré-processamento textual para TTS.
4.11. Estado atual da implementação
Kokoro já foi validado como direção principal do MVP.
Piper permanece como fallback aprovado.
Problemas atuais de latência inicial e silêncios entre chunks devem ser tratados dentro da Fase 13A.
---
5. Limites de autonomia do Antigravity
O Antigravity pode decidir autonomamente:
a melhor implementação da abstração de TTS;
o desenho interno dos providers;
os arquivos necessários dentro do escopo da fase;
os detalhes de capability detection;
o nível de fallback entre backends;
a forma exata de separar narrador do livro e voz do assistente;
a melhor camada de pré-processamento textual, desde que dentro do escopo;
as otimizações internas do pipeline de reprodução contínua compatíveis com a Fase 13A.
O Antigravity não pode decidir autonomamente:
forçar dependência obrigatória de nuvem;
exigir GPU como condição de funcionamento do MVP;
trocar o foco da fase para voice cloning/multi-speaker/podcast;
usar VibeVoice como backend principal;
reestruturar o reader de forma ampla só por causa do TTS;
introduzir dependência pesada externa sem necessidade justificada;
trocar o backend principal do MVP sem nova decisão humana explícita.
---
6. Política obrigatória de experiência e confiabilidade
6.1. A experiência de narração deve melhorar perceptivelmente
O MVP deve produzir melhoria perceptível em pelo menos:
naturalidade
pausas
fluidez
separação entre voz do livro e do assistente
6.2. O reader não pode travar
TTS deve operar sem bloquear a thread principal.
qualquer backend pesado deve passar por fallback ou execução controlada.
6.3. O texto deve ser preparado para fala
A camada de pré-processamento deve tratar no mínimo:
diálogos com travessão
aspas
listas
números
pontuação complexa
abreviações
artefatos de OCR
ruído visual inútil para fala
6.4. Transparência de backend ativo
o app deve deixar claro qual backend está ativo ou, no mínimo, se houve fallback relevante.
6.5. Critério corretivo da Fase 13A
A estabilização da Fase 13 exige correção explícita de:
tempo até o primeiro áudio (TTFB);
silêncios perceptíveis entre chunks;
confiabilidade dos controles Play/Pause/Stop.
---
7. Política obrigatória de hardware e fallback
7.1. Capability detection obrigatória
Antes de usar backend avançado, verificar:
disponibilidade real do backend;
capacidade de CPU/GPU/memória;
impacto na latência;
risco de travamento da interface.
7.2. Hierarquia aprovada
```text
Tier A → Qwen3-TTS (quando suportado e realmente vantajoso)
Tier B → Kokoro (padrão de qualidade do MVP)
Tier C → Piper (fallback leve e robusto)
Tier D → Sherpa-ONNX / runtime alternativo quando aplicável
```
7.3. Regra de degradação graciosa
Se o sistema não puder oferecer a melhor qualidade:
degradar para um backend mais leve;
manter a funcionalidade de narração;
preservar a fluidez do reader;
evitar travamento ou silêncio inesperado.
7.4. Regra específica da Fase 13A
se Kokoro não aquecer ou iniciar dentro do limiar aceitável, o sistema pode/ deve fazer fallback para Piper em hardware fraco ou cenário de baixa latência.
---
8. Estado atual da fase e subfase 13A
8.1. Situação atual
A Fase 13 já teve implementação inicial suficiente para validar:
qualidade ótima de voz com Kokoro;
viabilidade da arquitetura multi-backend;
direção correta de produto.
8.2. Subfase corretiva oficial
Fica oficialmente registrada a subfase:
Fase 13A — Otimização do Pipeline de Narração
Escopo específico da Fase 13A
warmup/pré-warm do Kokoro;
fila contínua de áudio entre chunks;
concatenação/crossfade curto entre blocos;
revisão do chunking para leitura contínua;
fallback automático para Piper por SLO de latência;
robustez de Play/Pause/Stop.
Regra
A Fase 13 não deve ser considerada plenamente estabilizada até a conclusão da Fase 13A.
---
9. Arquivos que podem ser criados ou alterados
O Antigravity pode criar/alterar arquivos necessários dentro do escopo da fase, incluindo, se necessário:
```text
src/core/tts/
  base_tts_provider.py                 [NOVO]
  piper_provider.py                    [NOVO]
  kokoro_provider.py                   [NOVO]
  qwen3_tts_provider.py                [NOVO]
  sherpa_onnx_provider.py              [NOVO]
  text_preprocessor.py                 [NOVO]
  tts_router.py                        [NOVO]

src/gui/
  audio_reader_controls.py             [NOVO ou extensão]
  main_window.py
  reader_view.py
  styles.py

data/config.json
tests/test_text_preprocessor.py        [NOVO]
tests/test_tts_router.py               [NOVO]
tests/test_audio_reader_integration.py [NOVO]
docs/agents/phase_13_audio_reader_2_0_mvp.md      [referência]
docs/agents/phase_13_execution_contract.md        [referência]
```
Regra de contenção
Não criar arquivos adicionais desnecessários.
Criar apenas o que:
sustenta a implementação;
sustenta testes;
melhora segurança/manutenção;
reduz ambiguidade operacional.
---
10. Testes obrigatórios da fase
O Antigravity deve concluir a fase com testes que cubram no mínimo:
10.1. Funcionais
sintetizar texto com backend padrão;
alternar backend sem quebrar o reader;
separar narrador do livro e do assistente;
aplicar velocidade/configuração sem corromper saída;
validar Play/Pause/Stop.
10.2. Pré-processamento
diálogos com travessão melhorados;
texto técnico continua inteligível;
pontuação complexa não quebra a narração;
ruído de OCR/texto bruto é reduzido.
10.3. Hardware / fallback
backend avançado cai para backend mais leve;
backend leve continua funcional em máquina modesta;
UI não trava aguardando síntese.
10.4. Regressão
reader continua estável;
agente proativo continua estável;
flashcards/Anki continuam estáveis;
OCR, tradução offline e RAG continuam sem regressão.
10.5. Smoke test humano
EPUB curto
PDF técnico
trecho com diálogo
trecho de resposta do assistente
troca de voz/configuração
medição de TTFB e continuidade entre blocos
---
11. Critérios de conclusão da fase
A Fase 13 só pode ser considerada pronta quando:
```text
[ ] Existe uma abstração de TTS local.
[ ] O backend padrão do MVP está funcional.
[ ] Há fallback útil sem travar o reader.
[ ] Há distinção entre narrador do livro e voz do assistente.
[ ] O pré-processamento melhorou a leitura de texto real.
[ ] O app continua local-first.
[ ] Há testes cobrindo os fluxos relevantes.
[ ] O plano de rollback está claro.
```
Critério adicional para o estado atual da fase
A implementação atual da Fase 13 só será considerada plenamente estabilizada quando a Fase 13A concluir:
warmup satisfatório;
melhoria de TTFB;
redução de silêncios entre chunks;
controles Play/Pause/Stop confiáveis.
---
12. Rollback obrigatório
Se a implementação falhar em qualquer critério de aceite ou introduzir regressão relevante:
restaurar o backend anterior de narração;
remover ou desabilitar a nova camada TTS por configuração;
preservar a experiência atual do reader sem o upgrade da Fase 13.
Regra prática
Melhor manter a narração antiga do que introduzir uma narração melhor em tese, mas instável na prática.
---
13. Resultado esperado da execução autônoma
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
14. Definição de pronto deste contrato
Este contrato estará pronto quando:
```text
[ ] For salvo como docs/agents/phase_13_execution_contract.md
[ ] Estiver referenciado no prompt da Fase 13
[ ] O Antigravity puder executar a fase sem novas confirmações humanas
[ ] O documento técnico da Fase 13 continuar acessível como referência principal
[ ] A Fase 13A estiver registrada como subfase corretiva oficial
```