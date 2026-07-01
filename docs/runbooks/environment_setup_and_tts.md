# Runbook: Configuração de Ambiente e TTS
## Procedimentos de Instalação, Alinhamento de CUDA e Troubleshooting de GPU

Este runbook orienta desenvolvedores e usuários na instalação do ambiente Python do projeto, configuração do suporte à aceleração por hardware (CUDA), resolução de incompatibilidades com a GPU Blackwell (`sm_120`) e diagnóstico do pipeline de Text-to-Speech (TTS).

---

## 1. Configuração do Ambiente Virtual (venv)

O projeto opera localmente usando um ambiente virtual Python isolado.

### Passos de Inicialização do Zero (Windows)
1.  Abra o terminal (PowerShell) no diretório raiz do projeto:
    ```powershell
    python -m venv venv
    ```
2.  Ative o ambiente virtual:
    ```powershell
    .\venv\Scripts\Activate.ps1
    ```
3.  Instale os pacotes requeridos básicos:
    ```powershell
    pip install -r requirements.txt
    ```

---

## 2. Configuração do PyTorch e CUDA

O TTS neural do projeto (`Kokoro-82M`) depende do PyTorch para execução dos pesos do modelo.

### Instalação Padrão (Estável - CUDA 12.4)
Se a sua GPU for compatível com capacidades de computação até `sm_90` (RTX 30xx, RTX 40xx, etc.):
```powershell
pip install torch torchvision torchaudio --index-url https://download.pytorch.org/whl/cu124
```

### Verificação de Compatibilidade CUDA
Após a instalação, verifique a conexão física com a placa executando:
```powershell
.\venv\Scripts\python -c "import torch; print(f'CUDA disponível: {torch.cuda.is_available()}'); print(f'GPU: {torch.cuda.get_device_name(0) if torch.cuda.is_available() else \"N/A\"}')"
```

---

## 3. Troubleshooting de GPU Blackwell (sm_120)

Se o seu sistema possuir uma placa da arquitetura NVIDIA Blackwell (ex: RTX 5060 Ti, compute capability `sm_120`), o build padrão estável do PyTorch (`2.6.0+cu124`) reportará um aviso de incompatibilidade e o Kokoro Provider degradará automaticamente para a execução em **CPU** (baseline degradada provisória).

### Receita Experimental para Habilitar GPU Blackwell (Nightly - CUDA 12.8)
Caso queira forçar a execução acelerada por GPU na arquitetura Blackwell:
1.  **Faça backup das dependências atuais** (opcional, recomendado):
    ```powershell
    .\venv\Scripts\pip freeze > pre_nightly_freeze.txt
    ```
2.  **Instale os builds experimentais de pré-lançamento do PyTorch com suporte a CUDA 12.8**:
    ```powershell
    .\venv\Scripts\pip install --pre torch torchvision torchaudio --index-url https://download.pytorch.org/whl/nightly/cu128
    ```
3.  **Verifique se a arquitetura foi registrada**:
    ```powershell
    .\venv\Scripts\python -c "import torch; print('sm_120' in torch.cuda.get_arch_list())"
    ```
    *Se retornar `True`, o suporte a Blackwell está ativo na GPU e o Kokoro Provider rodará em modo `cuda` nativo.*

---

## 4. Parametrização e Configuração dos Providers TTS

O comportamento do player e dos fallbacks de voz é regido pelo arquivo de configurações local `data/config.json`.

```json
{
  "database_path": "data/library.db",
  "chroma_db_path": "data/chroma_db",
  "tts_provider_priority": ["kokoro", "piper", "pyttsx3"],
  "default_voice": "pf_dora",
  "tts_rate": 1.0,
  "tts_volume": 1.0
}
```

### 4.1 Kokoro-82M (Tier B - Default de Qualidade)
*   **Dependências:** `pip install kokoro sounddevice numpy`.
*   **Cache Offline:** Os pesos e arquivos de configuração ficam salvos no cache local do HuggingFace (geralmente em `C:\Users\<usuario>\.cache\huggingface\hub\models--hexgrad--Kokoro-82M`). O aplicativo roda 100% offline definindo `os.environ["HF_HUB_OFFLINE"] = "1"`.
*   **Warmup Inicial:** Na primeira execução, o roteador carrega a pipeline em background. O warmup completo leva $\approx 1.8\text{s}$ em CPU e $< 200\text{ms}$ em GPU.

### 4.2 Piper (Tier C - Fallback de Performance)
Se a latência do Kokoro ultrapassar o SLO do projeto (3.0s), o roteador degrada para o Piper.
*   **Instalação de Vozes:** Coloque os arquivos `.onnx` e `.onnx.json` da voz do Piper (ex: `pt_BR-faber-medium`) no diretório configurado em `data/config.json`.
*   **Executável CLI:** O roteador tenta ler o Piper via biblioteca Python; se não encontrar, tenta localizar o executável `piper.exe` no PATH.

### 4.3 pyttsx3 (Legacy SAPI5 - Último Recurso)
*   **Funcionamento:** Utiliza o sintetizador de voz nativo do Windows (SAPI5). Não requer downloads de modelos e serve como a rede de segurança final do sistema.

---

## 5. Script de Validação Rápida de TTS

Para validar se o pipeline de áudio está funcional e rastrear o provider final efetivamente utilizado, execute:
```powershell
.\venv\Scripts\python C:\Users\jefer\.gemini\antigravity-ide\brain\24fc3980-5065-48a8-a483-fb49d0973caf\scratch\validate_kokoro.py
```
O script testará a importação, warmup e inferência real, imprimindo a classificação do estado do Kokoro e o provider final usado.
