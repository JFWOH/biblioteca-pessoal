# Matriz Mínima de Compatibilidade (Compatibility Matrix)

Este documento mapeia os requisitos mínimos e as configurações recomendadas de runtime, dependências e modelos de inteligência artificial necessários para a execução e homologação da **Biblioteca Pessoal Inteligente**.

---

## 1. Ambiente de Runtime e Sistemas Operacionais

| Componente | Requisito Mínimo | Configuração Recomendada | Observações |
|---|---|---|---|
| **Python** | `>= 3.10` | `3.11.x` (64-bit) | Testado ativamente em Python 3.11.9. Evitar Python 3.12+ devido a possíveis problemas de compilação de extensões nativas C/C++. |
| **Windows** | Windows 10 | Windows 11 (64-bit) | Suporte completo a drivers de som (SAPI5) e execução CUDA para modelos locais. |
| **macOS** | macOS Monterey | macOS Sonoma (Apple Silicon) | Execução de Ollama em Metal. Suporte a SAPI legado via AppleScript fallback no áudio. |
| **Linux** | Ubuntu 22.04 LTS | Ubuntu 24.04 LTS | Suporte a ALSA/PulseAudio para backend de áudio. |

## 2. Modelos de IA Locais (Ollama)

| Finalidade | Modelo Mínimo | Modelo Recomendado | Observações |
|---|---|---|---|
| **Chat / RAG** | `gemma:2b` | `gemma4:e4b` / `gemma:7b` | O uso de modelos com menos de 2 bilhões de parâmetros pode comprometer a habilidade de seguir esquemas de Tool Calling e JSON estruturado. |
| **Embeddings** | `nomic-embed-text` | `nomic-embed-text` | Padrão do ChromaDB do projeto. Não alterar sem reindexar completamente o banco vetorial local. |
| **Ollama Service**| `ollama >= 0.2.0` | `ollama >= 0.3.x` | Garantir que o daemon está rodando na porta `11434` e possui suporte ativo a concurrency limit. |

## 3. Backends e Engines de TTS

| Engine | Tipo / Nível | Requisitos / Dependências | Observações |
|---|---|---|---|
| **Kokoro-82M** | Tier B (Primary High-Quality) | `torch >= 2.0`, `transformers >= 4.33`, `numpy` | Excelente qualidade expressiva. Requer vetorização NumPy para evitar atraso (TTFB) em CPU de baixo desempenho. |
| **Piper** | Tier C (Fast Fallback) | Executável Piper local ou wrapper Python | Ativado automaticamente se a latência do Kokoro exceder o SLO de 3.0 segundos. |
| **pyttsx3** | Tier D (Legacy System) | SAPI5 (Windows), NSSpeechSynthesizer (macOS), espeak (Linux) | Fallback em nível de sistema operacional. Voz sintética mecânica tradicional. |

## 4. Banco de Dados e Busca Semântica

- **SQLite:** `sqlite >= 3.35.0` (com suporte ativo à extensão FTS5 para busca textual indexada de alto desempenho).
- **ChromaDB:** `chromadb >= 0.4.0, < 1.0` (banco de dados vetorial embutido rodando localmente sem necessidade de servidor dedicado).

## 5. Limitações Conhecidas e Restrições Físicas
1. **Performance em CPU Pura (sem GPU):** A síntese do Kokoro em CPU de computadores antigos pode apresentar Time To First Byte (TTFB) próximo ao limite do SLO (3.0s). Nestes cenários, o Piper ou pyttsx3 assumirão a execução de forma transparente.
2. **Latência de Warmup Inicial:** A primeira chamada do Kokoro ou do modelo Ollama após ligar a máquina pode demorar alguns segundos a mais devido à leitura em disco para carregar os pesos na memória RAM.
3. **Limitação de Concorrência SQLite:** Embora o banco de dados esteja hardened com single-writer lock, escritas concorrentes intensas vindas do `AudioWorker`, `RAGWorker` e UI principal podem criar pequenos atrasos na interface se o banco não for consolidado no modo WAL.
4. **Sem Suporte a Rede/Telemetria:** O aplicativo opera 100% offline. Ele não possui drivers para sincronização de dados via internet ou monitoramento de falhas remoto.
