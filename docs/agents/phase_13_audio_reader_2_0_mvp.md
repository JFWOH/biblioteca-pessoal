---
title: "Plano Técnico Completo — Fase 13: Audio Reader 2.0 / Narração Expressiva"
status: "Referência ativa de implementação (corrigida e atualizada)"
version: "1.1-final"
date: "2026-05-30"
audience:
Engenharia
Produto
QA
UX/UI
Acessibilidade
Segurança
Antigravity Agent
owner: "Engenharia de Produção / Antigravity Agent"
related_report: "Roadmap do projeto — Biblioteca Pessoal Inteligente"
rollback_marker: true
mode: "PRODUCTION ENGINEERING"
---
Plano Técnico Completo — Fase 13: Audio Reader 2.0 / Narração Expressiva
> **Objetivo deste documento:** registrar a proposta técnica consolidada da Fase 13, dedicada a elevar significativamente a qualidade da leitura narrada do aplicativo Biblioteca Pessoal Inteligente, com foco em:
>
> - naturalidade de voz
> - prosódia
> - entonação
> - conforto em leitura longa
> - separação entre narrador do livro e voz do assistente
> - manutenção do princípio local-first
> - fallback por hardware e degradação graciosa
>
> **Importante:** esta é a versão **corrigida e atualizada** do documento. Ela mantém a visão original da Fase 13, mas já incorpora o estado real da implementação inicial e a abertura da **Fase 13A — Otimização do Pipeline de Narração**.
---
0. Decisão executiva
```text
Decisão: APROVAR a Fase 13 — Audio Reader 2.0 / Narração Expressiva — como frente oficial do roadmap.
Status: referência ativa de implementação.
Caminho recomendado: camada de abstração de TTS com múltiplos backends locais, fallback por hardware e pipeline de áudio resiliente.
Prioridade: melhorar perceptivelmente a experiência de narração sem comprometer responsividade, privacidade e estabilidade do reader.
Princípio central: a leitura narrada deve soar melhor, iniciar de forma aceitável e manter continuidade entre trechos.
```
Resumo da decisão
A qualidade de narração deve ser tratada como UX central, não como detalhe técnico.
A solução deve permanecer local-first.
O projeto deve usar camada unificada de TTS, não acoplamento rígido a uma única engine.
O sistema deve separar:
Narrador do livro
Voz do assistente
A fase deve prever:
fallback por hardware
degradação graciosa
otimização do pipeline de reprodução
---
1. Contexto
O projeto já consolidou:
leitura local
OCR local
tradução offline
agente contextual
agente proativo
ferramentas de estudo / integração com Anki
UI do reader mais madura
Com isso, a qualidade da narração tornou-se uma frente de alto valor perceptível. Em especial, para um app de leitura, a qualidade da fala impacta diretamente:
conforto de uso prolongado
acessibilidade
retenção do usuário
percepção geral de inteligência e polimento do sistema
O panorama atual de TTS local em 2026 sustenta uma estratégia em camadas:
Piper como baseline rápido/offline
Kokoro como salto de naturalidade com baixo footprint
Qwen3-TTS como trilha avançada de controle expressivo e multilíngue
Sherpa-ONNX como runtime/infraestrutura offline multiplataforma
1.1. Estado atual após a implementação inicial da Fase 13
A implementação inicial da Fase 13 já produziu um resultado importante:
Kokoro foi escolhido como backend principal do MVP por qualidade perceptível muito superior.
Piper permaneceu como fallback leve e rápido.
Qwen3-TTS foi avaliado, mas não adotado como backend principal do MVP.
1.2. Problemas encontrados após a implementação inicial
Apesar do salto de qualidade com Kokoro, foram identificados problemas operacionais:
demora para começar a leitura
silêncios perceptíveis entre trechos/chunks
necessidade de correção/fortalecimento dos controles de reprodução
Esses pontos motivam a subfase corretiva:
Fase 13A — Otimização do Pipeline de Narração
A Fase 13A não substitui a Fase 13. Ela é uma subfase corretiva focada em:
warmup/prefetch do backend
fila contínua de áudio
concatenação/crossfade curto entre chunks
revisão do chunking
fallback automático para Piper por SLO de latência
restauração/robustez de Play/Pause/Stop
---
2. Objetivo da fase
Elevar a qualidade da leitura falada no aplicativo por meio de:
melhor engine de TTS
melhor pré-processamento de texto
melhor separação entre tipos de narração
melhor adaptação a hardware local
fallback seguro e previsível
pipeline de reprodução contínua e estável
---
3. Escopo
Incluído
criação de uma abstração de TTS local
suporte a múltiplos backends de TTS
avaliação comparativa e integração mínima com pelo menos:
Piper
Kokoro
Qwen3-TTS
Sherpa-ONNX
distinção entre:
narrador do livro
voz do assistente
melhoria do pré-processamento do texto para leitura
modos de voz/configuração
fallback por hardware
smoke tests e testes de regressão
otimização do pipeline de reprodução contínua (Fase 13A)
Fora de escopo
clonagem de voz personalizada
multivoz dramática completa / teatro sonoro
uso obrigatório de GPU
integração cloud-first
sync de preferências com múltiplos dispositivos
upgrade do Audio Reader para multimodal conversacional completo
narração multi-speaker longa no MVP
VibeVoice como backend principal nesta fase
---
4. Arquitetura proposta
```text
Reader / Assistant Output
        |
        v
Text Preprocessor
        |
        v
TTS Provider Abstraction
        |
        +--> Piper Provider
        +--> Kokoro Provider
        +--> Qwen3-TTS Provider
        +--> Sherpa-ONNX Provider
        |
        v
TTS Router + Capability Detection
        |
        v
Audio Output Pipeline
        |
        +--> Warmup / Preload
        +--> Chunk Scheduling
        +--> Queue / Prebuffer
        +--> Merge / Crossfade
        |
        v
Playback Controls / UI
```
Componentes principais
4.1. Text Preprocessor
Responsável por:
limpar artefatos do texto
melhorar pausas
tratar diálogos
expandir abreviações quando necessário
ajustar números, citações e pontuação para fala
preparar estilos diferentes para:
leitura longa
explicação curta
resposta do assistente
4.2. TTS Provider Abstraction
Camada unificada para múltiplos motores de TTS locais.
Deve expor, por exemplo:
`synthesize(text, mode, voice_profile, language)`
`available_voices()`
`supports_streaming()`
`health_check()`
`latency_profile()`
4.3. Audio Output Pipeline
Responsável por:
streaming ou bufferização
warmup do backend
fila/buffer contínuo de chunks
concatenação/crossfade curto entre blocos
normalização de volume
manipulação de interrupção/cancelamento
coexistência com outros sons do app
---
5. Estratégia de produto
5.1. Dois perfis de narração
Narrador do livro
Características desejadas:
mais estável
menos efusivo
confortável para leitura longa
ritmo consistente
pausas bem resolvidas
continuidade entre trechos
Voz do assistente
Características desejadas:
mais curta
mais clara
mais didática
melhor para explicar observações, contexto e respostas
menor latência possível
5.2. Modos sugeridos
Leitura Serena
Leitura Técnica
Explicação Didática
Leitura Expressiva (quando o backend suportar bem)
---
6. Estratégia de backend e priorização operacional
6.1. Backend padrão do MVP
Kokoro
Kokoro é o backend padrão de qualidade do MVP nesta fase.
Motivos:
ótima naturalidade
footprint pequeno
boa relação qualidade/performance
viável em ambiente local
resultado real já validado na implementação inicial
6.2. Fallback leve
Piper
Piper é o backend de fallback leve e rápido.
Motivos:
CPU-friendly
robusto
rápido
adequado quando a UX exige resposta imediata ou hardware é modesto
6.3. Trilha avançada opcional
Qwen3-TTS
Qwen3-TTS permanece como trilha avançada opcional, não como dependência básica do MVP.
Motivos:
forte suporte multilíngue
controle expressivo avançado
streaming e baixa latência em cenários ideais
útil como backend premium futuro
6.4. Runtime / infraestrutura
Sherpa-ONNX
Sherpa-ONNX pode ser usado como camada de runtime / infraestrutura quando fizer sentido técnico.
Motivos:
empacotamento offline multiplataforma
padronização de deploy local
apoio a modelos ONNX em cenários heterogêneos
---
7. Papel do VibeVoice
Avaliação
VibeVoice é tecnicamente impressionante por focar em:
áudio longo
multi-speaker
geração expressiva
conversação longa com forte naturalidade
Decisão
Não usar VibeVoice como engine principal do MVP da Fase 13.
Motivo
perfil mais pesado
mais voltado a geração longa e multi-speaker
maior risco de inflar escopo
melhor tratado como trilha futura/experimental
Uso futuro sugerido
podcasts / leitura dramatizada
leitura de diálogos
narrativas muito longas
modo “audiobook premium”
---
8. Text Preprocessing (obrigatório)
O ganho de qualidade não virá apenas da troca de engine.
É obrigatório adicionar ou revisar uma camada de pré-processamento textual.
Deve cobrir no mínimo
diálogos com travessão
aspas
ponto e vírgula
dois-pontos
listas
números
abreviações
quebras de linha estranhas
artefatos de OCR
marcas de rodapé/referência inúteis para fala
Objetivo
Melhorar:
pausas
fluidez
inteligibilidade
prosódia
---
9. UX proposta
Configurações do usuário
Adicionar preferências no app para:
engine preferida
voz do livro
voz do assistente
velocidade
intensidade/expressividade (quando suportado)
fallback automático
Regras de UX
o sistema deve deixar claro qual backend está ativo
se houver fallback, isso deve ser tratado de forma transparente e discreta
o leitor não pode travar esperando TTS pesado
a leitura contínua do livro deve priorizar conforto e continuidade
a voz do assistente pode priorizar menor latência
---
10. Arquivos envolvidos (propostos)
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
docs/agents/phase_13_audio_reader_2_0_mvp.md
```
---
11. Testes necessários
11.1. Funcionais
sintetizar texto com backend padrão
trocar backend sem quebrar o reader
separar narrador do livro e voz do assistente
ajustar velocidade e manter integridade
validar Play / Pause / Stop
11.2. Qualidade mínima
texto com diálogo soa melhor após pre-processamento
pontuação complexa não quebra a fala
trechos longos continuam inteligíveis
gaps entre chunks ficam aceitáveis
11.3. Hardware / fallback
backend avançado cai para backend mais leve
máquina modesta continua funcional
TTS não bloqueia a UI
fallback para Piper funciona quando o SLO de latência do Kokoro é violado
11.4. Regressão
reader continua estável
agente proativo continua estável
flashcards/Anki continuam estáveis
OCR/tradução/RAG continuam sem regressão
11.5. Smoke test humano
leitura de EPUB
leitura de PDF
trecho com diálogo
trecho técnico
observação do assistente narrada
troca entre vozes
medição de TTFB e continuidade entre blocos
---
12. Riscos identificados
Escopo inflado
tentar resolver toda a área de voz de uma vez.
Mitigação: abstração + MVP simples.
Latência excessiva em backends avançados
Mitigação: fallback por hardware.
Qualidade boa, mas pipeline ruim
Mitigação: warmup, fila contínua, merge/crossfade e chunking adequado.
Pré-processamento ruim degradar o texto
Mitigação: testes específicos de normalização textual.
Misturar voz do livro com voz do assistente
Mitigação: perfis separados desde o início.
Thread/lifecycle incorreto no playback
Mitigação: revisão de worker, fila e estado da UI.
---
13. Critérios de aceite
A Fase 13 só pode ser aceita se:
```text
[ ] Existe uma abstração de TTS local.
[ ] O sistema suporta múltiplos backends ou, no mínimo, foi preparado para isso.
[ ] Há distinção entre narrador do livro e voz do assistente.
[ ] O pré-processamento melhorou a leitura de texto real.
[ ] Há fallback por hardware.
[ ] O reader não trava por causa do TTS.
[ ] A experiência de narração soa perceptivelmente melhor.
[ ] O app continua local-first.
[ ] Há plano de rollback claro.
```
Critério adicional para estado atual da fase
A implementação inicial da Fase 13 só será considerada plenamente estabilizada quando a Fase 13A concluir:
warmup satisfatório
melhoria de TTFB
redução de silêncios entre chunks
controles Play/Pause/Stop confiáveis
---
14. Critérios de rejeição
Rejeitar a fase se ocorrer qualquer item:
```text
[ ] A narração continua tão ruim quanto antes.
[ ] O TTS trava a UI.
[ ] Não existe fallback útil.
[ ] A voz do assistente e a do livro viram uma experiência confusa.
[ ] O escopo foi inflado para multi-speaker/voice cloning sem necessidade.
[ ] O app passa a depender de nuvem para narrar.
[ ] O pipeline permanece com início ruim e buracos audíveis entre blocos.
```
---
15. Pontos que exigem validação humana
Backend padrão do MVP
Piper
Kokoro
outro
Recomendação: Kokoro como padrão de qualidade e Piper como fallback leve.
Perfil padrão do livro
sereno
técnico
expressivo
Recomendação: sereno.
Voz do assistente
mesma engine do livro ou engine própria
Recomendação: engine compartilhada, voz/perfil diferente.
Qwen3-TTS no MVP
incluir no MVP ou deixar como trilha avançada opcional
Recomendação: manter como trilha avançada opcional, não como dependência básica.
---
16. Estratégia de implementação sugerida
Iteração 1 — abstração e baseline
criar camada TTS provider
integrar Piper ou Kokoro
adicionar text preprocessor
Iteração 2 — UX e separação de perfis
livro vs assistente
controles mínimos
Iteração 3 — fallback e capability detection
roteamento entre providers
fallback por hardware
Iteração 4 — backend avançado
adicionar Qwen3-TTS como provider avançado opcional
validar qualidade real
Iteração 5 — polish
smoke tests humanos
revisão adversarial
ajustes finos de prosódia/preprocessamento
Iteração 6 — Fase 13A (otimização do pipeline)
warmup/pré-warm
fila contínua entre chunks
merge/crossfade curto
revisão do chunking
fallback por SLO para Piper
correções de Play/Pause/Stop
---
17. Recomendações finais
Recomendações principais
Tratar a Fase 13 como melhoria de experiência principal, não como feature secundária.
Começar por uma camada de TTS unificada.
Não acoplar o app a uma única engine.
Usar Kokoro + Piper como eixo inicial do MVP.
Tratar Qwen3-TTS como trilha avançada.
Deixar VibeVoice fora do MVP.
Tratar a Fase 13A como correção obrigatória do pipeline real de uso.
Ordem recomendada
```text
1. Criar abstração de TTS
2. Melhorar pré-processamento textual
3. Integrar backend local baseline
4. Separar narrador do livro e narrador do assistente
5. Adicionar fallback
6. Validar backend avançado
7. Otimizar pipeline de reprodução contínua (13A)
```
---
18. Definição de pronto deste documento
Este documento estará pronto quando:
```text
[ ] For salvo como docs/agents/phase_13_audio_reader_2_0_mvp.md
[ ] O roadmap referenciar a Fase 13
[ ] O documento for usado como base do prompt autônomo da Fase 13
[ ] A Fase 13A estiver registrada como subfase corretiva oficial
```
---
19. Referências externas estáveis
Qwen3-TTS
GitHub: https://github.com/QwenLM/Qwen3-TTS
Technical Report (arXiv): https://arxiv.org/abs/2601.15621
Kokoro
Model card: https://huggingface.co/hexgrad/Kokoro-82M
Inference library: https://github.com/hexgrad/kokoro
Piper
Exemplo de uso/local voice assistant: https://www.promptquorum.com/power-local-llm/build-local-voice-assistant-2026
Sherpa-ONNX
GitHub: https://github.com/k2-fsa/sherpa-onnx
TTS docs: https://k2-fsa.github.io/sherpa/onnx/tts/index.html
VibeVoice
GitHub: https://github.com/microsoft/VibeVoice
Microsoft Research: https://www.microsoft.com/en-us/research/publication/vibevoice-expressive-podcast-generation-with-next-token-diffusion/