# 🔊 Audio Reader — Módulo de TTS Local Offline

Este documento descreve as especificações técnicas, arquitetura e uso do módulo de leitura de áudio (**Audio Reader**) local e offline integrado ao aplicativo **Biblioteca Pessoal Inteligente**.

---

## 🎯 1. Objetivo
Oferecer leitura em voz alta (Text-to-Speech - TTS) de páginas, capítulos ou trechos de livros selecionados de forma totalmente **local-first** e **offline**. 

O objetivo primordial é garantir:
- **Acessibilidade:** Permitir leitura confortável por voz de múltiplos formatos (EPUB, PDF).
- **Privacidade Absoluta:** O conteúdo lido nunca sai da máquina do usuário (sem APIs na nuvem).
- **Flexibilidade Arquitetural:** Uma interface desacoplada que aceita múltiplos motores de voz e não interfere no fluxo de IA (RAGEngine).

---

## 🏛️ 2. Arquitetura e Pipeline de Execução

O processamento do texto segue um fluxo rigoroso dividido em camadas isoladas:

```
Texto Bruto (PDF/EPUB) 
       │
       ▼
[Text Chunker] ──► clean_text_for_tts()   (Remove quebras de linha e hifens artificiais)
       │
       ▼
[Text Chunker] ──► split_text_for_tts()   (Fração inteligente em blocos < max_chars)
       │
       ▼
[AudioReaderService] ─────────────────────► Controla a fila e estados de reprodução (stop/pause)
       │
       ▼
[TTSBackend Interface] ───────────────────► Abstração plugável
       │
       ├──► Pyttsx3Backend ───────────────► Motor inicial local (pyttsx3)
       └──► FakeTTSBackend ───────────────► Usado em testes automatizados headless
```

### A. Limpeza de Hifens em PDF (`clean_text_for_tts`)
Textos extraídos de arquivos PDF frequentemente contêm hifens de partição silábica artificiais gerados no final das linhas de texto (ex: `com-\nputador`). A reprodução por áudio desse texto literal resultaria em uma leitura pausada e artificial.
- O pipeline local utiliza a regra regex `(?<=\w)-\s*\n\s*(?=\w)` para de forma conservadora aglutinar palavras separadas por hifens de quebra de linha.
- Hifens semânticos legítimos como `segunda-feira`, `e-mail` e `state-of-the-art` são **rigorosamente preservados**.

### B. Limpeza de Marcadores de Referência/Notas de Rodapé (`clean_reference_markers_for_tts`)
Textos frequentemente contêm citações, referências bibliográficas ou notas de rodapé sobrescritas, em colchetes ou convertidas em dígitos normais durante a extração de PDFs (ex: `importantes.²`, `importantes. 2`, `texto<sup>2</sup>` ou `texto.[2][3]`). Para evitar que esses marcadores sejam soletrados ou lidos indevidamente pelo sintetizador de voz (TTS):
- Remove sobrescritos numéricos adjacentes a pontuações (ex: `importantes.²` -> `importantes.`, `texto².` -> `texto.`).
- Remove dígitos normais que funcionam como notas de rodapé após pontuações (ex: `importantes. 2` ou `importantes.2` -> `importantes.`), garantindo por meio de asserções negativas `(?<!\d)` e verificações semânticas (letra maiúscula seguinte ou fim do parágrafo) que números legítimos em datas, decimais e contagens não sejam afetados.
- Remove tags HTML `<sup>` de referência bibliográfica (ex: `texto<sup>2</sup>` -> `texto`).
- Remove citações numéricas em colchetes isolados ou múltiplos adjacentes que seguem pontuações (ex: `texto.[2]` -> `texto.`, `texto. [2][3]` -> `texto.`).
- **Preservação de Fórmulas e Unidades:** Utiliza placeholders temporários para garantir que expoentes e potências matemáticos/físicos legítimos sejam **rigorosamente preservados** (ex: `m²`, `m³`, `E=mc²`, `x² + y²`).

### C. Divisão em Blocos (`split_text_for_tts`)
Para mitigar a latência de cancelamento/parada e garantir boa responsividade, textos longos são quebrados em blocos (chunks) curtos parametrizados por `max_chunk_chars` (default `600` caracteres).
1. O texto é limpo e separado em parágrafos.
2. Parágrafos que cabem no limite são enviados como blocos individuais (mantendo a pausa natural do parágrafo).
3. Parágrafos muito longos são decompostos sequencialmente em sentenças (frases).
4. Sentenças longas são fracionadas por palavras.

---

## ⏹️ 3. Semântica Realista de Parada (`stop()`)
A interrupção de reprodução de voz em motores nativos do sistema operacional (SAPI5/eSpeak/NSSpeech) opera com buffers de áudio enviados diretamente à placa de som. Por esta razão:
- O método `stop()` do `AudioReaderService` opera sob a garantia de **best-effort** (melhor esforço).
- Ao acionar `stop()`:
  1. A fila de leitura pendente é **descartada instantaneamente**.
  2. Um flag de cancelamento síncrono impede que novos blocos de texto sejam empurrados para a reprodução.
  3. O serviço chama `backend.stop()` síncrono para interromper o som ativo da placa.
  4. O retorno ao chamador da GUI é imediato, evitando travamentos visuais.
- **Nota técnica:** O uso de blocos moderadamente curtos (600 caracteres) é a melhor técnica para reduzir a latência de áudio já carregado no buffer nativo.

---

## 🛠️ 4. Instalação e Requisitos

### Dependência Principal
O leitor utiliza `pyttsx3>=2.99`, adicionado de forma opcional e tratada de maneira defensiva no construtor de `Pyttsx3Backend`.

Para rodar a leitura real local, instale a biblioteca no ambiente virtual:
```bash
venv\Scripts\pip install pyttsx3
```

### Requisitos por Sistema Operacional (Offline Nativo)
- **Windows:** Utiliza a API nativa **SAPI5**. Funciona "out of the box" sem pacotes adicionais.
- **macOS:** Utiliza o sintetizador nativo **NSSpeechSynthesizer** (`nsss`). Funciona nativamente.
- **Linux:** Utiliza o motor open-source **eSpeak** (`espeak-ng`). Pode exigir instalação prévia no sistema de arquivos:
  ```bash
  sudo apt-get install espeak-ng libespeak1
  ```

---

## 🧪 5. Execução de Testes

Os testes unitários e de integração de contrato não emitem som real e rodam perfeitamente em modo **headless** através de mock do `FakeTTSBackend`.

Execute os testes rápidos do áudio:
```bash
venv\Scripts\python -m pytest tests/test_audio_reader_service.py -q
venv\Scripts\python -m pytest tests/test_tts_backend_contract.py -q
```

Execute a suíte geral do projeto:
```bash
venv\Scripts\python -m pytest
```

---

## ⚠️ 6. Limitações Conhecidas
1. **Pause/Resume:** Devido a instabilidades de threads em implementações multiplataforma do `pyttsx3`, as funções de `pause()` e `resume()` operam de forma passiva (no-op) nesta versão inicial MVP.
2. **Latência de Parada Ativa:** A interrupção imediata do som ativo depende exclusivamente do driver de som nativo gerenciado pelo sistema operacional.
