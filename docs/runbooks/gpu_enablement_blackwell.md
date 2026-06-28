# Runbook: Habilitação de GPU Blackwell (NVIDIA RTX 50-series sm_120)
## Guia de Instalação e Ativação do Pipeline TTS Acelerado por GPU no Windows

Este runbook orienta desenvolvedores e usuários na habilitação segura de aceleração por GPU (CUDA 12.8) para o pipeline de TTS neural (modelo Kokoro-82M) em sistemas que possuam hardware NVIDIA com arquitetura Blackwell (`sm_120`).

---

## 1. Pré-Requisitos de Hardware e Software

Para que a aceleração por hardware Blackwell funcione corretamente no Windows, certifique-se de que os itens abaixo estão presentes:
1. **Placa de Vídeo (GPU):** Placa NVIDIA RTX série 50 (ex: RTX 5060 Ti ou superior, compute capability `12.0`/`sm_120`).
2. **Driver Gráfico NVIDIA:** Versão do driver instalada no host compatível com CUDA 12.8 ou superior.
3. **SO:** Windows 10/11 de 64-bit.
4. **Python:** Versão 3.11.x instalada localmente.

---

## 2. Passo-a-Passo de Instalação e Ativação

O processo de instalação garante o alinhamento com as dependências oficiais do projeto, instalando primeiro a baseline e aplicando em seguida o delta experimental de GPU.

### Passo 1: Criação e Ativação da Venv Isolada (Lab)
Recomenda-se criar um ambiente virtual isolado para não poluir a venv estável padrão do projeto:
```powershell
# Criar venv de laboratório
python -m venv venv-gpu-lab

# Ativar venv no PowerShell
.\venv-gpu-lab\Scripts\Activate.ps1
```

### Passo 2: Instalação da Baseline do Projeto
Antes de qualquer modificação, instale todas as dependências oficiais do projeto a partir do `requirements.txt`:
```powershell
pip install -r requirements.txt
```

### Passo 3: Instalação das Dependências de GPU Blackwell (CUDA 12.8)
Instale a build homologada do PyTorch com suporte nativo a CUDA 12.8 a partir do repositório oficial do PyTorch. A rota foi verificada via dry-run e encontra-se online no repositório de wheels do PyTorch:
```powershell
pip install torch==2.11.0+cu128 --index-url https://download.pytorch.org/whl/cu128
```
*(Nota: O download possui aproximadamente 2.75 GB de tamanho devido às bibliotecas CUDA embarcadas).*

### Passo 4: Instalação das Bibliotecas de TTS adicionais
Garanta que as bibliotecas necessárias para a reprodução de áudio e síntese Kokoro estejam instaladas na nova venv:
```powershell
pip install kokoro sounddevice numpy
```

---

## 3. Validação do Runtime e Suporte Blackwell

Para verificar se a instalação do PyTorch CUDA 12.8 reconheceu a placa Blackwell física e as instruções de kernel `sm_120`:

1. **Checagem Rápida no Interpretador:**
   ```powershell
   python -c "import torch; print(f'CUDA disponível: {torch.cuda.is_available()}'); print(f'Arquitetura sm_120 suportada: { \"sm_120\" in torch.cuda.get_arch_list() }')"
   ```
   *Ambos os comandos devem retornar `True`.*

2. **Execução do Script de Diagnóstico TTS:**
   O projeto fornece um script seguro para validar a pipeline completa e coletar métricas reais de síntese (warmup, TTFB, tempo de processamento) sem travar threads de áudio em ambientes headless:
   ```powershell
   python tools/validate_kokoro_gpu.py
   ```
   **Resultado Esperado nos Logs:**
   - `provider_reported_device: cuda`
   - `kokoro_state_classification: adequado/validado`
   - `provider_effectively_used: Kokoro`
   - `TTS_ROUTER_TTFB_MS: ~148 ms` (SLO de TTFB $< 3000\text{ms}$ atendido com folga).

---

## 4. Troubleshooting e Mecanismo de Fallback

### O que acontece se o PyTorch CUDA falhar?
O subsistema de TTS neural do projeto foi construído com resiliência baseada em falhas (graceful degradation) de acordo com a **ADR-005**:
1. Se a inicialização do driver CUDA falhar ou se o dispositivo CUDA se tornar indisponível em runtime (ex: suspensão do sistema), o `TTSRouter` captura o erro interno.
2. O roteador marca o backend do Kokoro GPU como não saudável (`healthy = False`).
3. O roteador redireciona automaticamente todas as chamadas subsequentes de síntese para a baseline estável em **CPU** ou degrada para o provider de backup **Piper**.
4. O áudio do aplicativo continuará sendo reproduzido graciosamente para o usuário.

### Como desfazer as alterações e retornar à baseline CPU?
Para restaurar a baseline original de CPU estável do projeto, basta reativar a venv estável original do projeto (`venv\Scripts\Activate.ps1`) ou reinstalar o PyTorch padrão de CPU:
```powershell
pip install torch --index-url https://download.pytorch.org/whl/cpu
```
