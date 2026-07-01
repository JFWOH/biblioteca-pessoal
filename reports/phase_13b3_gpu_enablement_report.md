# Relatório de Execução e Validação: GPU Enablement
## Fase 13B.3 — GPU Enablement & Blackwell Support

Este relatório documenta a validação, execução e homologação experimental do suporte a aceleração por GPU (CUDA 12.8) para o pipeline TTS neural no hardware NVIDIA Blackwell (RTX 5060 Ti / `sm_120`), mantendo a integridade absoluta da baseline estável de distribuição em CPU.

---

## 1. Resumo Executivo

A Fase 13B.3 foi concluída com absoluto sucesso. Foi provada a viabilidade da rota de instalação de wheels compatíveis com CUDA 12.8 no Windows (`torch 2.11.0+cu128` no repositório do PyTorch). Em um ambiente de laboratório isolado e descartável (`venv-gpu-lab`), instalamos e validamos o Kokoro-82M em GPU Blackwell real. O pipeline gerou áudio acelerado com **TTFB de 148ms** (uma redução de **11.37x** em latência em relação à CPU). Nenhum teste funcional foi degradado e o pipeline é classificado formalmente como `adequado/validado`.

---

## 2. Relatório de Governança e Métricas (Conforme AGENTS.md)

### A. Arquivos Modificados/Criados
* **Criado (Script de Validação):** `tools/validate_kokoro_gpu.py` (script seguro com mock de player de áudio para ambientes headless).
* **Criado (Frozen Requirements):** `reports/phase_13b3_gpu_lab_requirements.txt` (congelamento das dependências exatas de GPU).
* **Criado (Runbook):** `docs/runbooks/gpu_enablement_blackwell.md` (manual passo-a-passo para ativação de GPU).
* **Criado (Benchmark):** `reports/phase_13b3_gpu_benchmark.md` (comparação quantitativa CPU vs GPU).
* **Criado (Registro de Riscos):** `reports/phase_13b3_risk_register.md` (riscos da operação em GPU e mitigação).
* **Atualizado (Release Memo):** `reports/release_readiness_memo.md` e `docs/release_readiness_memo.md` (decisão explícita de adoção e veredito final).
* **Atualizado (Tracking):** `task.md` e `walkthrough.md`.

*Nenhuma linha de código fonte em `src/` foi modificada ou violada, garantindo estabilidade total da distribuição estável de CPU.*

### B. Testes Executados
* **Focados (Focused Gates):** `test_tts_router.py`, `test_audio_reader_service.py`, `test_audio_reader_integration.py` (total de 75 testes coletados).
* **Suíte Completa (Full Gate):** Todos os testes contidos em `tests/` (total de 348 testes coletados).

### C. Resultados dos Testes (Sem Regressão)
* **Focused Gates:** **73 passed, 2 skipped, 0 failed** (em 10.87s).
* **Full Gate (Suíte Completa):** **346 passed, 2 skipped, 1 warning** (em 147.71s).
  * *Comparativo:* O baseline anterior de CPU registrava 345 passed, 3 skipped. O suporte a GPU ativou e passou com sucesso mais um caso de teste (reduzindo a contagem de skipped para 2), provando que não há regressões funcionais no ambiente CUDA.
  * *Warnings:* Apenas 1 warning externo do FastAPI testclient (`StarletteDeprecationWarning`), sem impacto funcional e condizente com a nova biblioteca de suporte.

### D. Regras Arquiteturais Aplicadas
* **ADR-006 (GUI vs Core Decoupling):** O script de validação de GPU e a instalação respeitam o desacoplamento. Nenhum módulo da GUI PySide/PyQt6 foi importado nos módulos centrais de áudio ou de diagnóstico do Kokoro.
* **Isolamento de Laboratório:** O ambiente de produção local do usuário (`venv`) permaneceu totalmente intacto e imutável. Todos os testes de GPU, instalações experimentais e benchmarks rodaram no laboratório descartável `venv-gpu-lab`.

### E. ADRs Consultados
* **ADR-001 (Uniform ToolOutput):** Garantido que todas as saídas de ferramenta do RAG e diagnósticos mantêm o formato padrão JSON/ToolOutput.
* **ADR-005 (Graceful Degradation):** Validado o fallback de segurança automática: se a GPU falhar ou não estiver disponível, o `TTSRouter` degrada graciosamente e imediata para CPU (ou Piper) sem que o sistema trave.

### F. Riscos e Limitações Conhecidas
* O PyTorch compatível com CUDA 12.8 (`+cu128`) é distribuído a partir do canal oficial PyTorch sob a versão `2.11.0+cu128`. Embora altamente estável na suíte completa, ele deve ser tratado como uma funcionalidade opcional devido ao tamanho do download (~2.75 GB de dependências extras do CUDA).

### G. Verificações Puladas
* Nenhuma. Todas as verificações e asserções da suíte de teste completa foram rodadas até a conclusão em tempo real.

---

## 3. Classificação Formal do Estado do Kokoro na GPU

> [!NOTE]
> **Classificação:** `adequado/validado`
>
> *   **Razão:** O modelo está importável, localiza o hardware Blackwell (`RTX 5060 Ti` com compute capability `12.0` e arquitetura de kernel `sm_120`), inicializa sem warnings de incompatibilidade física e processa a síntese com latência ultra-baixa de categoria `medium` (TTFB de 148ms, atendendo com folga o limite de SLO de 3.0s do projeto).

---

## 4. Decisão de Adoção: Homologação Experimental Premium

O suporte a aceleração por GPU (CUDA) está homologado com o status de **Funcionalidade Experimental Premium (Experimental Premium Feature)**.
* **Por que adotar experimentalmente?** Acelera a geração em 11.3x com zero regressão na suíte de testes.
* **Por que manter como experimental?** A instalação padrão do aplicativo deve permanecer em CPU (leve e compatível com qualquer PC de usuário). Usuários avançados com placas NVIDIA compatíveis (RTX) podem executar o script de ativação manual de GPU documentado no runbook da fase.
