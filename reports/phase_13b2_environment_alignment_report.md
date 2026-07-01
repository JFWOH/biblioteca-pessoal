# Relatório de Alinhamento de Ambiente
## Fase 13B.2 — Environment Alignment

---

## 1. Resumo Técnico

Este relatório descreve o diagnóstico conclusivo do ambiente de execução local para o subsistema de conversão de texto em fala (TTS) neural e orquestração PyTorch. O objetivo foi identificar e mapear as causas das advertências de incompatibilidade com a GPU do desenvolvedor e o comportamento do processamento em CPU.

---

## 2. Configuração do Hardware e SO

*   **Sistema Operacional:** Windows 10 build 26200 (64-bit).
*   **Processador (CPU):** Intel/AMD com suporte x86_64.
*   **Memória RAM:** 31.9 GB Total (14.4 GB Disponíveis).
*   **Placa de Vídeo (GPU):** NVIDIA GeForce RTX 5060 Ti.
*   **VRAM Total:** 15.93 GB (16 GB nominal).
*   **Capacidade de Computação CUDA (Compute Capability):** `sm_120` (Arquitetura NVIDIA Blackwell).

---

## 3. Diagnóstico de PyTorch e CUDA

A versão instalada do PyTorch no ambiente virtual do projeto (`g:\PROGRAMAS PYTHON\Biblioteca-pessoal\venv`) é:
*   **Versão do PyTorch:** `2.6.0+cu124` (Versão estável compilada com CUDA 12.4).
*   **Disponibilidade CUDA reportada pelo PyTorch:** `True`.
*   **Lista de Arquiteturas CUDA Pre-compiladas no Binário do PyTorch (arch_list):**
    `['sm_50', 'sm_60', 'sm_61', 'sm_70', 'sm_75', 'sm_80', 'sm_86', 'sm_90']`

### O Conflito Físico
A arquitetura Blackwell (`sm_120`) é muito mais recente que a Hopper/Ada Lovelace (`sm_90`). O binário estável do PyTorch `2.6.0+cu124` não possui os kernels pré-compilados para a capacidade de computação `12.0` (Blackwell). 

Ao importar o PyTorch e acessar o driver de vídeo, o PyTorch emite a seguinte advertência formal:
```
NVIDIA GeForce RTX 5060 Ti with CUDA capability sm_120 is not compatible with the current PyTorch installation.
The current PyTorch install supports CUDA capabilities sm_50 sm_60 sm_61 sm_70 sm_75 sm_80 sm_86 sm_90.
```

### Comportamento do Core (KokoroProvider)
Para evitar que a execução de síntese de áudio falhasse em runtime com o erro `RuntimeError: CUDA error: no kernel image is available` ao tentar instanciar tensores em GPU, o backend `KokoroProvider` do projeto executa uma verificação preventiva (`_check_cuda_compatibility()`):
1. Ele compara a capacidade de computação retornada pelo driver (`sm_120`) com a lista suportada pelo PyTorch (`arch_list`).
2. Como não há compatibilidade direta, ele força o dispositivo de execução a se inicializar como **CPU**.
3. **Status do Ambiente:** A execução em CPU constitui a nossa **baseline degradada provisória** para o TTS neural nesta versão de distribuição.

---

## 4. Análise de Mitigações para Blackwell/sm_120

Para habilitar a aceleração por hardware (GPU CUDA) em arquiteturas Blackwell, existem duas abordagens possíveis:

### Opção A: Atualização para PyTorch Nightly (CUDA 12.8)
A NVIDIA Blackwell é totalmente suportada a partir do CUDA 12.8. O canal experimental/preview de desenvolvimento do PyTorch disponibiliza pacotes contendo kernels compilados para `sm_120`.
*   **Comando de Instalação:**
    ```powershell
    .\venv\Scripts\pip install --pre torch torchvision torchaudio --index-url https://download.pytorch.org/whl/nightly/cu128
    ```
*   **Prós:** Habilita a execução nativa na GPU RTX 5060 Ti, reduzindo o TTFB do Kokoro para $< 100\text{ms}$.
*   **Contras/Bloqueios:**
    1. O tamanho total do download ultrapassa **3 GB**, representando risco de falha de download ou estouro de espaço em disco em conexões limitadas.
    2. O canal `nightly` (preview) é experimental, podendo conter bugs de concorrência ou quebras em outras bibliotecas que dependem de PyTorch estável.
    3. Exige drivers NVIDIA atualizados no host ($566.36+$).

### Opção B: Manutenção em CPU (Fallback Degradado Provisório)
Manter a execução em CPU como baseline provisória.
*   **Prós:** 100% estável, sem downloads volumosos e em conformidade estrita com a integridade atual do venv e suíte de testes.
*   **Contras:** TTFB inicial elevado ($\approx 1.7\text{s}$) e maior consumo de CPU no host durante a síntese.

**Decisão de Homologação:** Mantida a **Opção B** como padrão na release v0.1.10, com a receita da **Opção A** documentada no runbook para uso opcional e avançado pelo desenvolvedor/usuário.

---

## 5. Histórico e Auditoria de Comandos

| Comando | Escopo | Output Obtido | Conclusão |
|---|---|---|---|
| `python -c "import torch; print(torch.cuda.is_available())"` | Validação de CUDA | `True` | O driver e a biblioteca estão fisicamente conectados. |
| `python -c "import torch; print(torch.cuda.get_arch_list())"` | Lista de capacidades | `['sm_50', ..., 'sm_90']` | Arquitetura Blackwell (`sm_120`) não é suportada pela build estável local. |
| `validate_kokoro.py` | Execução real | `device = cpu` | O provider degradou graciosamente para CPU sem quebrar a execução. |
