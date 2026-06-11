# Runbook: Testes e Validação do Sistema
## Procedimentos de Garantia de Qualidade e Gates de Release

Este runbook orienta desenvolvedores e engenheiros de QA locais na execução da suíte de testes automatizados e nas etapas manuais de validação do RAG e do subsistema de áudio/TTS.

---

## 1. Mapeamento da Suíte de Testes Existente

O repositório possui uma cobertura robusta de testes unitários e de integração (348 testes no total). Os principais arquivos estão classificados por domínio:

- **RAG & Agente Cognitivo:**
  - `tests/test_rag_orchestrator.py`
  - `tests/test_rag_policy.py`
  - `tests/test_rag_trace_logger.py`
  - `tests/test_rag_engine.py`
  - `tests/test_rag_eval_harness.py`
- **TTS & Leitor de Áudio:**
  - `tests/test_tts_router.py`
  - `tests/test_audio_reader_service.py`
  - `tests/test_audio_reader_integration.py`
  - `tests/test_tts_backend_contract.py`
- **Banco de Dados e Infraestrutura:**
  - `tests/test_database.py`
  - `tests/test_database_extended.py`
  - `tests/test_concurrency.py`
  - `tests/test_config.py`
- **Readers e Parsers de Documento:**
  - `tests/test_readers.py`
  - `tests/test_cbz_reader.py`
  - `tests/test_pdf_reader_ocr_integration.py`
- **Tradução Offline:**
  - `tests/test_translation_service.py`
  - `tests/test_translation_integration.py`

---

## 2. Testes de Gate Bloqueantes para Release Privado

Nenhuma nova versão (release privado local) deve ser gerada sem a aprovação completa nos seguintes testes chaves de regressão (se presentes no repositório):

| Arquivo de Teste | Área Coberta | Impacto se Falhar |
|---|---|---|
| `tests/test_rag_orchestrator.py` | Orquestrador RAG | Quebra o fluxo do chat inteligente. |
| `tests/test_rag_policy.py` | Policy Engine | Risco de mutações de UI inseguras/invadir escopo. |
| `tests/test_rag_trace_logger.py`| Observabilidade | Falha no registro estruturado de traces. |
| `tests/test_audio_reader_service.py`| Player de Áudio | Quebra a reprodução contínua (play/pause/stop). |
| `tests/test_tts_router.py` | Roteador do TTS | Quebra a conversão de voz, warmup ou fallback. |
| `tests/test_database.py` | Acesso ao Banco | Inviabiliza persistência de anotações e progresso. |
| `tests/test_concurrency.py` | Concorrência SQLite | Risco de deadlocks ou corrupção do banco local. |

---

## 3. Como Executar os Testes

### Execução de Testes Focados (Recomendado Primeiro)
Sempre execute primeiro os testes do módulo específico que você está validando. Exemplo:
```powershell
python -m pytest tests/test_tts_router.py
```

Para rodar o conjunto mínimo de testes gate:
```powershell
python -m pytest tests/test_rag_orchestrator.py tests/test_rag_policy.py tests/test_rag_trace_logger.py tests/test_tts_router.py tests/test_audio_reader_service.py tests/test_database.py tests/test_concurrency.py
```

### Execução da Suíte Completa
Se o ambiente de release local possuir todas as dependências (incluindo o daemon do Ollama ativo para testes que exigem conexões locais), execute:
```powershell
python -m pytest tests/
```
*Se a suíte completa não puder ser finalizada por restrições de ambiente (por exemplo, GPU/Ollama indisponíveis no servidor de build), documente o limitador exato.*

---

## 4. Validação Manual do Pipeline RAG e TTS

Para garantir que a UX do leitor local está em perfeito estado antes de liberar a distribuição:

### Passo A: Validação do Áudio/TTS
1. Abra a aplicação rodando `python -m src.main`.
2. Abra qualquer livro de teste (PDF ou EPUB) cadastrado na biblioteca.
3. Clique em **Play** no botão de áudio localizado na barra de leitura.
4. **Verifique:**
   - O áudio começa a tocar de forma expressiva (Warmup funcionando em background).
   - O primeiro trecho de som deve sair em até 3 segundos (SLO do TTFB).
   - Clique em **Pause** e verifique se o áudio interrompe instantaneamente.
   - Clique em **Play** novamente e verifique a retomada de onde parou.

### Passo B: Validação do Chat Agentic RAG
1. Abra o painel lateral do assistente RAG.
2. Digite a consulta: *“Quais os principais temas abordados na página atual?”*
3. **Verifique:**
   - O RAG executa com o status de iterações/rounds visível.
   - O modelo gera a resposta baseando-se estritamente nas fontes locais.
   - Caso o modelo proponha um destaque visual, verifique se a marcação é renderizada corretamente sobre a página do leitor (Policy Engine permitindo ação local segura).
   - Abra a pasta `data/traces/` e certifique-se de que um novo arquivo de trace JSONL foi criado e preenchido.
