# Roteiro E5 — validação do pacote portátil em máquina limpa

> Ciclo jul/2026-E. Executar após gerar o ZIP (rodada E4). Ideal: VM Windows
> 10/11 SEM Python, SEM GPU e com disco lento — o pior caso do tester real.

## 0. Gerar o pacote (máquina de build, com rede)

```bash
venv\Scripts\python.exe -m src.tools.build_package --out build\BibliotecaPessoal
```

Conferir ao final: `runtime\` (python embutido + deps CPU), `src\`,
`resources\`, `Manual - Biblioteca Pessoal.pdf`, `LEIA-ME.txt`,
`Biblioteca Pessoal.bat`, `Diagnostico.bat`, `portable.flag`,
`data\hf_cache\hub\models--hexgrad--Kokoro-82M\` (pré-seed),
`data\piper\models\pt_BR-faber-medium.onnx` + `.onnx.json` (voz de RESERVA,
rodada ago/2026 — os DOIS arquivos, um `.onnx` órfão quebra a síntese) e o
`.zip` ao lado da pasta. **Vetos:** nada de `venv\`, `data\chroma_db`,
`library.db`, `tests\`, `docs\agents\`, `.git`.

Sanidade rápida ainda na máquina de build:
`build\BibliotecaPessoal\runtime\python.exe -c "import src.main"` (deve sair
sem erro e sem baixar nada).

## 1. Instalação (na máquina limpa)

- [ ] Extrair o ZIP em `Documentos` (caminho COM espaço e acento, de
      propósito) e dar dois cliques em "Biblioteca Pessoal".
- [ ] SmartScreen: "Mais informações → Executar assim mesmo" funciona.
- [ ] Splash aparece de imediato; janela abre sem "Não está respondendo".
- [ ] O manual está na estante como livro nº 1 (e o PDF abre da pasta).

## 2. Núcleo sem IA (deve funcionar 100% offline)

- [ ] Importar 1 PDF e 1 EPUB (arrastar e soltar) → capas e metadados ok.
- [ ] Ler, virar página, marcar página, destacar, anotar.
- [ ] Pesquisa global encontra por título E por conteúdo (após indexação FTS
      do importado).
- [ ] **Ouvir página** funciona SEM internet (Kokoro pré-embutido — este é o
      teste do pré-seed). Primeira narração pode demorar ~1 min em HDD.
- [ ] Estatísticas registram a sessão de leitura.

## 3. IA opcional (com rede)

- [ ] `Ctrl+R` → wizard "Instalar Ollama Automaticamente" → barra de
      progresso → conclui sem terminal.
- [ ] Pergunta ao assistente sobre o manual → resposta com citação de página.
- [ ] Traduzir Página → consentimento do download do NLLB (~2,4 GB) →
      progresso → tradução aparece; reabrir a página traduz na hora (cache).
- [ ] Configurações → 🔌 Integrações: comando MCP copia; caminhos apontam
      para DENTRO do pacote (runtime\python.exe, raiz extraída).

## 4. Robustez

- [ ] Fechar e reabrir: dados persistem; manual NÃO reimporta.
- [ ] Fechar o app segundos após abrir (durante init da IA) → sem crash.
- [ ] `Diagnostico.bat` roda com console e fecha com `pause`.
- [ ] Mover a pasta inteira de lugar → tudo segue funcionando (portátil).

## Registro

Anotar: tempo até a janela (1ª e 2ª abertura), specs da máquina, e qualquer
mensagem/tela inesperada (print). Falhas viram itens do ciclo pós-feedback.
