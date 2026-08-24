"""
Proactive Trigger Engine
Decides whether an observation should be generated based on intensity and page content.
"""

# Política de frequência por nível — (páginas mínimas desde o último disparo,
# palavras mínimas na página). Cada disparo é uma chamada ao LLM local, então a
# tabela É o custo do proativo por página lida.
#
# Revisão da Onda Q (ago/2026), antes → depois:
#   Leve      5 → 8 páginas  (0,20 → 0,13 chamada/página)
#   Moderado  2 → 3 páginas  (0,50 → 0,33 chamada/página)
#   Estudo    1 → 1 página   (inalterado: "quase toda página" é o contrato do nível)
# Leve e Moderado estavam colados no Estudo — o gap maior separa os rótulos e
# corta ~1/3 das chamadas sem mudar o que cada nível promete. Revisita de página
# não gasta orçamento: o serviço filtra antes (memo de sessão + continuidade),
# então o gap conta páginas NOVAS de leitura.
_POLICY = {
    "Leve": (8, 150),
    "Moderado": (3, 100),
    "Estudo": (1, 0),
}

# Piso de conteúdo comum a todos os níveis: abaixo disso a página é capa,
# ilustração ou folha de rosto — não há o que observar.
_MIN_CHARS = 200


class ProactiveTriggerEngine:
    def __init__(self):
        self._last_triggered_page = -100

    def reset(self):
        self._last_triggered_page = -100

    def should_trigger(self, page_text: str, current_page: int, intensity: str) -> bool:
        """
        Avalia heuristicamente se o texto atual e as configurações justificam o disparo do modelo.
        """
        if not page_text or intensity == "Desligado":
            return False

        if len(page_text.strip()) < _MIN_CHARS:
            return False

        policy = _POLICY.get(intensity)
        if policy is None:
            return False
        min_gap, min_words = policy

        if current_page - self._last_triggered_page < min_gap:
            return False
        if len(page_text.split()) <= min_words:
            return False

        self._last_triggered_page = current_page
        return True
