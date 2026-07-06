"""Padrões compartilhados das chamadas ao Ollama.

Núcleo puro (ADR-006) — importável tanto pelo core quanto pelos workers da GUI.
"""

# Mantém os modelos residentes na VRAM entre interações. Sem isto o Ollama
# descarrega o modelo ~5 min após a última chamada e a próxima ação de IA paga
# o reload a frio (segundos) ANTES do raciocínio começar. 30 min cobre pausas
# de leitura típicas sem prender a VRAM indefinidamente (revisão de engenharia
# 2026-07-05, §1.1). Aceito por /api/chat, /api/embed e /api/generate.
OLLAMA_KEEP_ALIVE = "30m"
