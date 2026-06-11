# Runbook: Recovery e Rollback Local
## Operações e Resolução de Falhas Críticas

Este runbook orienta o usuário final ou o engenheiro de testes em procedimentos de emergência, incluindo recuperação de banco de dados corrompido, inconsistências do ChromaDB, limpeza segura de traces locais e rollback do código.

---

## 1. Recuperação de Banco de Dados Corrompido (SQLite)

### Sintomas
- Erros de `DatabaseError: malformed` ou `sqlite3.DatabaseError: file is encrypted or is not a database`.
- Falha na inicialização do leitor ou impossibilidade de gravar anotações.

### Procedimento de Recuperação
1. **Fazer backup do arquivo corrompido:**
   ```powershell
   Copy-Item -Path "data/library.db" -Destination "data/library.db.bak" -Force
   ```
2. **Reconstrução Simples via CLI (se o SQLite estiver no PATH):**
   ```powershell
   sqlite3 data/library.db ".recover" | sqlite3 data/library_recovered.db
   ```
   Se a reconstrução for bem sucedida, substitua o arquivo original:
   ```powershell
   Remove-Item -Path "data/library.db" -Force
   Rename-Item -Path "data/library_recovered.db" -NewName "library.db"
   ```
3. **Recuperação de Emergência (Rebuild Total do Banco):**
   Caso o banco esteja irreparável:
   - Exclua o arquivo `data/library.db`.
   - Execute o script de inicialização para gerar um banco de dados vazio e estruturado:
     ```powershell
     python -c "from src.core.database import init_db; init_db()"
     ```
   - O aplicativo recriará as tabelas e o usuário poderá reimportar seus livros e gerar novos metadados.

---

## 2. Reconciliação e Reparo de Ingestão (ChromaDB)

### Sintomas
- A busca semântica (RAG) retorna resultados de livros deletados ou falha ao buscar livros recém-importados.
- Inconsistência entre a tabela `indexing_state` do SQLite e as coleções no ChromaDB.

### Procedimento de Reparo
1. **Limpeza da Persistência Vetorial:**
   - Feche a aplicação.
   - Delete com segurança o diretório do ChromaDB local:
     ```powershell
     Remove-Item -Path "data/chroma_db/" -Recurse -Force
     ```
2. **Reindexação Completa de Livros:**
   - Ao reiniciar o aplicativo, o ChromaDB será recriado automaticamente vazio.
   - Para reindexar os livros e sincronizar os índices, execute o serviço de reconciliação nativo:
     ```powershell
     python -c "from src.core.rag.document_indexer_service import DocumentIndexerService; DocumentIndexerService().reconcile_all_indexes()"
     ```

---

## 3. Limpeza Segura de Traces (Housekeeping de Logs)

### Sintomas
- Uso excessivo de espaço em disco na pasta `data/traces/` (milhares de arquivos JSONL acumulados).

### Procedimento de Limpeza
1. **Limpeza Manual Segura:**
   Você pode deletar os traces antigos sem medo, pois eles não são vitais para o funcionamento de leitura ou anotações do leitor.
   ```powershell
   Remove-Item -Path "data/traces/*.jsonl" -Force
   ```
2. **Executar Utilitário de Retenção Nativo (Fase 3):**
   O projeto já possui um script que retém apenas as 100 sessões mais recentes e limpa o resto automaticamente. Execute:
   ```powershell
   python -m src.tools.trace_retention --max-traces 100
   ```

---

## 4. Estratégia de Rollback de Código e Configuração

### Rollback de Versão/Commit (Git)
Se uma atualização de código quebrar a UI de forma catastrófica no ambiente local:
1. Identifique o último commit estável conhecido (ex. `v0.1.9` ou um hash específico):
   ```powershell
   git log --oneline -n 10
   ```
2. Faça o checkout para o estado anterior:
   ```powershell
   git reset --hard <HASH_ESTÁVEL>
   ```

### Rollback de Configurações (`config.json`)
Se o arquivo de configurações for corrompido ou apresentar caminhos inválidos:
1. Delete o arquivo `data/config.json`.
2. Reinicie o aplicativo. Ele regenerará um arquivo `config.json` com valores default seguros para o sistema.
