import logging
from typing import List, Dict, Any, Optional

logger = logging.getLogger(__name__)

def normalize_web_result(item: Dict[str, Any]) -> Optional[Dict[str, Any]]:
    """Normaliza um resultado cru de busca web extraindo de forma flexível as chaves
    de título, link de URL e texto do trecho (snippet/body).
    
    Retorna um dicionário padronizado: {'title': str, 'href': str, 'text': str}
    ou None se o resultado for inválido.
    """
    if not isinstance(item, dict):
        return None

    # 1. Extração flexível de Título
    title = item.get("title") or item.get("name") or item.get("headline") or "Sem título"
    title = str(title).strip()

    # 2. Extração flexível de URL/Link (não descartando por nomenclaturas)
    href = item.get("href") or item.get("url") or item.get("link") or item.get("url_link") or ""
    href = str(href).strip()

    # 3. Extração flexível de Corpo/Snippet
    text = item.get("body") or item.get("snippet") or item.get("description") or item.get("text") or item.get("abstract") or item.get("summary") or ""
    text = str(text).strip()

    # Valida que o resultado contém pelo menos link e algum conteúdo descritivo
    if not href and not text:
        return None

    return {
        "title": title,
        "href": href,
        "text": text
    }


def search_duckduckgo(query: str, provider_errors: List[str]) -> List[Dict[str, Any]]:
    """Executa a busca externa usando a biblioteca duckduckgo_search de forma flexível.
    
    Tenta múltiplos endpoints e instâncias para suportar diferentes versões instaladas.
    """
    # Tentativa 1: DDGS Context Manager / text (padrão moderno)
    try:
        from duckduckgo_search import DDGS
        with DDGS() as ddgs:
            raw_res = ddgs.text(query, max_results=5)
            if raw_res:
                return list(raw_res)
    except Exception as e:
        provider_errors.append(f"DDGS Context Manager / text falhou: {e}")

    # Tentativa 2: DDGS Legado sem Context Manager / text
    try:
        from duckduckgo_search import DDGS
        ddgs = DDGS()
        raw_res = ddgs.text(query, max_results=5)
        if raw_res:
            return list(raw_res)
    except Exception as e:
        provider_errors.append(f"DDGS Legado / text falhou: {e}")

    # Tentativa 3: DDGS answers (Instant answers API de fallback)
    try:
        from duckduckgo_search import DDGS
        with DDGS() as ddgs:
            raw_res = ddgs.answers(query)
            if raw_res:
                if isinstance(raw_res, list):
                    return list(raw_res)
                return [raw_res]
    except Exception as e:
        provider_errors.append(f"DDGS answers falhou: {e}")

    return []
