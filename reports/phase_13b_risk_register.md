# Registro de Riscos Remanescentes (Risk Register)
## Fase 13B — Core Hardening & Private Release Readiness

Este documento elenca os riscos técnicos e operacionais remanescentes priorizados para a distribuição local privada (private release) da **Biblioteca Pessoal Inteligente**.

---

## 1. Tabela de Riscos Priorizados

| ID Risco | Categoria | Descrição do Risco | Impacto | Probabilidade | Nível de Risco | Mitigação Recomendada |
|---|---|---|---|---|---|---|
| **RSK-01** | Desempenho | CPU local lenta resulta em latências de áudio do Kokoro superiores ao SLO de 3.0s, disparando fallbacks frequentes para o Piper. | Médio | Alta | **Alto** | Configurar o hardware para priorizar aceleração por GPU se disponível (CUDA/MPS) e instruir o usuário na escolha de vozes leves do Piper. |
| **RSK-02** | Dependência | Ausência de pacotes nativos de áudio (`kokoro`, `piper`) na instalação padrão de dependências do Python devido a restrições de compilação C++ local. | Médio | Alta | **Alto** | Fornecer instaladores pré-compilados (wheels) ou scripts de auto-setup automatizados para instalação desses pacotes no Windows. |
| **RSK-03** | Concorrência | Travamento temporário da interface gráfica (PyQt6) durante chamadas simultâneas de leitura/escrita pesadas no SQLite se não configuradas em WAL mode. | Alto | Baixa | **Médio** | Assegurar que o banco é inicializado no modo WAL e manter o wrapper do single-writer lock ativo em todas as escritas do RAG/TTS. |
| **RSK-04** | IA Local | Respostas inconsistentes ou "alucinações" do LLM (Gemma:2b/7b) sob queries complexas devido a limitações de tamanho de contexto ou capacidade de reasoning do modelo local. | Médio | Média | **Médio** | Aperfeiçoar o System Prompt e o token diet das ferramentas para preservar o histórico e maximizar o prefix caching no Ollama. |
| **RSK-05** | OS / Áudio | Incompatibilidade de drivers de áudio locais (SAPI5) em máquinas Windows desatualizadas, impedindo o fallback pyttsx3 de funcionar. | Baixo | Baixa | **Baixo** | Manter tratamento de erro silencioso para o player de áudio para evitar crash completo da interface de leitura em caso de ausência de driver. |

---

## 2. Planos de Resposta a Riscos de Alta Prioridade

### Resposta a RSK-01 (Latência Kokoro em CPU)
- **Ação:** O Roteador de TTS (`TTSRouter`) foi construído com chaveamento adaptativo dinâmico de 3.0s. Caso ocorra lentidão na CPU, a transição para o Piper garante a continuidade da narração sem intervenção do usuário.
- **Validação:** Monitorar o contador de `fallback_activated` em `reports/phase_13b_metrics.md` para calibrar se o limite do SLO de 3s é adequado ou necessita de ajuste para o hardware específico.

### Resposta a RSK-02 (Instalação Complexa de Dependências de Voz)
- **Ação:** Em `docs/private_release_checklist.md`, as instruções de setup foram divididas em pacotes core obrigatórios e opcionais (como tradução e voz).
- **Validação:** Homologar o instalador autônomo local em máquinas limpas sem Python previamente configurado antes da liberação final do pacote de distribuição.
