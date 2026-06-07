"""
Proactive Trigger Engine
Decides whether an observation should be generated based on intensity and page content.
"""

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

        if len(page_text.strip()) < 200:
            return False

        distance = current_page - self._last_triggered_page

        if intensity == "Leve":
            if distance >= 5:
                if len(page_text.split()) > 150:
                    self._last_triggered_page = current_page
                    return True
            return False

        elif intensity == "Moderado":
            if distance >= 2:
                if len(page_text.split()) > 100:
                    self._last_triggered_page = current_page
                    return True
            return False

        elif intensity == "Estudo":
            if distance >= 1:
                self._last_triggered_page = current_page
                return True
            return False

        return False
