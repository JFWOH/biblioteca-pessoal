# ADR-007: Audio Reader as Independent Local TTS Service

## Status
Accepted

## Context
O aplicativo precisa oferecer leitura em voz alta de textos de livros sem depender de internet e sem acoplar a funcionalidade ao RAGEngine.

Textos extraídos de PDF podem conter hifenização artificial de fim de linha e espaçamentos irregulares, prejudicando a experiência de TTS. Além disso, backends nativos usados por `pyttsx3` podem não garantir interrupção instantânea do áudio já em buffer.

## Decision
Implementar um módulo `src/core/audio/` com interface `TTSBackend` e backend inicial `Pyttsx3Backend`. A GUI deve interagir por worker/thread. O core de áudio não importa PyQt6 nem RAGEngine.

O pipeline de áudio aplica limpeza sintática leve e remoção de marcadores de notas de rodapé / referências bibliográficas (sobrescritos numéricos, tags sup HTML, citações em colchetes simples ou múltiplos, e dígitos regulares resultantes de conversão/extração indevida como ". 2" ou ".\n2") somente ao texto enviado ao TTS. Ao mesmo tempo, preserva de forma robusta expoentes matemáticos legítimos (m², mc²), fórmulas e números semânticos gerais (ex: datas, valores decimais, capítulos). O método `stop()` deve cancelar imediatamente a fila pendente e chamar `backend.stop()` em modo best-effort, sem prometer latência zero para áudio já entregue ao backend nativo.

## Consequences
- Mantém local-first.
- Preserva privacidade.
- Permite trocar backend no futuro.
- Evita bloqueio da GUI.
- Melhora a leitura de texto extraído de PDF e elimina a soletração indesejada de numeração de notas de rodapé.
- Garante a integridade matemática de unidades (m², m³) e equações (E=mc²) na leitura.
- Define uma semântica realista e testável para parada.
- Permite evolução futura para QtTextToSpeech, Piper ou Coqui.
