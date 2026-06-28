# Registro de Riscos Remanescentes e de GPU Enablement
## Fase 13B.3 — Risk Register

---

## 1. Mapeamento de Riscos Atuais

Este documento identifica os riscos remanescentes do sistema no final da Fase 13B.3, especificamente focados na ativação experimental do suporte a aceleração por GPU (CUDA 12.8) para hardware NVIDIA Blackwell (`sm_120`), detalhando as estratégias de contenção e mitigação aplicadas.

---

## 2. Tabela de Riscos Remanescentes e de GPU

| ID | Risco | Impacto | Probabilidade | Mitigação Aplicada / Recomendada | Status |
|---|---|---|---|---|---|
| **R-01** | **Tamanho de download excessivo das dependências CUDA (~2.75 GB)** | 🟡 Médio | 🔴 Alta | Manter a GPU como uma instalação premium opcional. A venv principal padrão de distribuição local permanece baseada apenas no PyTorch CPU (leve e de instalação rápida). | 🟢 Controlado |
| **R-02** | **Erros de alocação de memória na GPU (Out of Memory - OOM)** | 🔴 Alto | 🟢 Baixa | O modelo Kokoro-82M é extremamente leve (~82 milhões de parâmetros, consumindo menos de 350 MB de VRAM). O `TTSRouter` envia pedaços segmentados de texto, evitando o envio de textos gigantescos em uma única chamada. | 🟢 Mitigado |
| **R-03** | **Instabilidade ou regressões silenciosas decorrentes do uso da versão experimental PyTorch/cu128** | 🟡 Médio | 🟡 Média | Execução da suíte completa de 348 testes unitários e de integração na venv de laboratório. O resultado comprovou 346 testes passando com sucesso (nenhuma falha funcional). | 🟢 Validado |
| **R-04** | **Perda do dispositivo CUDA em runtime (Ex: suspensão do sistema ou reset de driver)** | 🔴 Alto | 🟢 Baixa | O `TTSRouter` monitora a saúde dos backends. Se a chamada para Kokoro via CUDA falhar ou disparar exceção, o roteador ativa o fallback gracioso em tempo real para os providers secundários (CPU fallback ou Piper) sem crashar o aplicativo. | 🟢 Mitigado |
| **R-05** | **Instalação em sistemas sem placa gráfica NVIDIA dedicada** | 🟡 Médio | 🔴 Alta | O instalador padrão do aplicativo não ativa a GPU. O runbook do Blackwell fornece as instruções explícitas de instalação manual exclusivamente para desenvolvedores e usuários que atendam aos requisitos mínimos de hardware. | 🟢 Controlado |

---

## 3. Matriz de Severidade

```
        PROBABILIDADE
        Alta      | R-01, R-05  |             |
        Média     |             | R-03        |
        Baixa     |             |             | R-02, R-04
                  +-------------+-------------+-------------
                      Baixo         Médio         Alto
                                  IMPACTO
```

---

## 4. Plano de Contingência para Falha de Runtime CUDA

Se em tempo de execução a GPU falhar, desconectar ou o driver entrar em colapso:
1. O backend `KokoroProvider` detectará a falha física na chamada e marcará o provider como `healthy = False` temporariamente.
2. O `TTSRouter` redirecionará a fila de síntese atual de forma transparente para a baseline CPU estável (ou outro provider ativo de backup).
3. O usuário continuará ouvindo o áudio normalmente, sofrendo apenas uma degradação de performance temporária (aumento na latência), sem sofrer travamento ou encerramento abrupto do aplicativo.
