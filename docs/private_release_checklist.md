# Checklist de Release Privado Local (Private Release Checklist)

Este checklist descreve os passos realistas e obrigatórios para preparar, implantar e validar uma nova versão local (distribuição privada) do aplicativo **Biblioteca Pessoal Inteligente** no ambiente do usuário final.

---

## 1. Verificação do Ambiente Mínimo
- [ ] **Sistema Operacional:** Windows 10/11 (64-bit) ou compatível.
- [ ] **Python:** Python 3.10 ou 3.11 instalado (3.11.9 recomendado) e adicionado ao PATH.
- [ ] **Espaço em Disco:** Mínimo de 10 GB livres (para modelos do Ollama, embeddings ChromaDB e vozes locais do TTS).

## 2. Dependências e Instalação
- [ ] **Instalação das dependências Python:**
  ```powershell
  python -m venv venv
  .\venv\Scripts\Activate.ps1
  pip install -r requirements.txt
  ```
- [ ] **Verificação de dependências opcionais:**
  - Garantir que `pip show torch` e `pip show transformers` mostram versões válidas caso a tradução offline (NLLB-200) seja requerida.
  - Verificar presença de `numpy` (exigido para a vetorização rápida do TTS).

## 3. Configuração do Daemon Ollama e Modelos
- [ ] **Status do Ollama:** Garantir que o serviço do Ollama está rodando localmente (verificar acessibilidade em `http://localhost:11434`).
- [ ] **Download de Modelos Requeridos:**
  - [ ] Modelo de Chat: `ollama pull gemma:2b` ou `ollama pull gemma:7b` (ou outro modelo de chat configurado em `config.json`).
  - [ ] Geração de Embeddings: `ollama pull nomic-embed-text`.
- [ ] **Validação rápida via CLI:**
  ```powershell
  ollama run gemma:2b "Olá"
  ```

## 4. Configuração dos Backends TTS
- [ ] **Kokoro-82M (Tier B):**
  - Garantir que o cache de modelos Hugging Face está acessível offline após o warmup inicial.
  - Verificar se a biblioteca `numpy` está operacional para evitar conversões lentas de áudio.
- [ ] **Piper (Tier C - Fallback):**
  - Confirmar que os arquivos de modelo de voz do Piper (`.onnx` e `.json`) estão na pasta local correta (definida em `config.json`).
  - Verificar integridade de executável/biblioteca do Piper na máquina de destino.
- [ ] **pyttsx3 (System Legado):**
  - Garantir funcionamento básico do SAPI5 (Windows Speech API) para fallback em nível de OS.

## 5. Integridade do Banco de Dados e Configurações
- [ ] **Banco Relacional:** Verificar se o arquivo `data/library.db` existe e não está corrompido. Em caso de novas migrações, executar script de teste de integridade.
- [ ] **Configurações:** Validar que o `data/config.json` possui os caminhos corretos e valores válidos para:
  - `database_path`
  - `chroma_db_path`
  - `tts_provider_priority`
  - `default_voice`
- [ ] **Banco Vetorial:** Certificar-se de que a pasta `data/chroma_db/` possui as coleções e permissões de escrita/leitura ativas.

## 6. Smoke Run (Inicialização)
- [ ] **Executar a aplicação local:**
  ```powershell
  python -m src.main
  ```
- [ ] **Validações na Interface Visual:**
  - [ ] A janela principal abre sem exibir exceptions no console.
  - [ ] O leitor carrega a lista de livros da biblioteca local.
  - [ ] Um livro PDF/EPUB de teste abre corretamente no visualizador.
  - [ ] Clicar no botão "Play" de áudio inicia a leitura sem travamentos na UI (warmup assíncrono funcional).
  - [ ] Fazer uma pergunta simples no chat RAG retorna resposta fundamentada nos metadados/livro atual.

## 7. Portão de Testes Mínimos Obrigatórios
- [ ] Executar testes focados de RAG e Banco de Dados:
  ```powershell
  python -m pytest tests/test_rag_orchestrator.py tests/test_database.py tests/test_concurrency.py
  ```
- [ ] Executar testes focados de Roteamento de Áudio e TTS:
  ```powershell
  python -m pytest tests/test_tts_router.py tests/test_audio_reader_service.py
  ```
- [ ] Executar a suíte completa se o ambiente permitir:
  ```powershell
  python -m pytest tests/
  ```

## 8. Estratégia de Rollback e Contingência
- [ ] **Backup pré-release:** Criar cópia de segurança de `data/library.db` e `data/config.json` antes de atualizar o código ou schemas de dados.
- [ ] **Reversão rápida:** Em caso de quebra silenciosa de código ou travamento de UI:
  - Executar rollback de commits problemáticos via Git: `git checkout tags/vX.Y.Z` ou `git revert <hash>`.
  - Restaurar backups de dados do SQLite.
  - Limpar caches temporários de traces acumulados.
