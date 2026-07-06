"""Sanitização do HTML de livros antes do QtWebEngine (revisão 2026-07-05 §2.1).

EPUBs são HTML arbitrário — frequentemente baixados da internet — e o leitor
os renderiza num QWebEngineView com JavaScript HABILITADO (o app usa
runJavaScript para features próprias: seleção, scroll, navegação). Sem
sanitização, qualquer <script> embutido no arquivo do livro executa com os
mesmos privilégios. Este módulo remove o que executa código e preserva todo
o resto (estrutura, estilos, imagens). Puro, sem Qt (ADR-006).
"""

from bs4 import BeautifulSoup

# Tags que executam código ou incorporam conteúdo ativo externo.
_ACTIVE_TAGS = ("script", "iframe", "object", "embed")

# Atributos que aceitam URL e podem carregar esquemas executáveis.
_URL_ATTRS = ("href", "src", "xlink:href", "action", "formaction", "data")

_BANNED_SCHEMES = ("javascript:", "vbscript:", "data:text/html")


def sanitize_book_html(html: str) -> str:
    """Remove vetores de execução de código do HTML de um livro.

    - tags ``<script>``/``<iframe>``/``<object>``/``<embed>`` (com conteúdo);
    - atributos de handler ``on*`` (onclick, onload, …);
    - URLs ``javascript:``/``vbscript:``/``data:text/html`` em href/src/etc.

    Conteúdo sem markup passa direto (TXT também flui por aqui).
    """
    if not html or "<" not in html:
        return html

    soup = BeautifulSoup(html, "html.parser")

    for tag in soup(_ACTIVE_TAGS):
        tag.decompose()

    for tag in soup.find_all(True):
        removed = [attr for attr in tag.attrs
                   if attr.lower().startswith("on")
                   or (attr.lower() in _URL_ATTRS and _is_banned_url(tag.attrs[attr]))]
        for attr in removed:
            del tag.attrs[attr]

    return str(soup)


def _is_banned_url(value) -> bool:
    # bs4 pode dar lista em atributos multivalor; normaliza para string.
    if isinstance(value, (list, tuple)):
        value = " ".join(str(v) for v in value)
    collapsed = "".join(str(value).lower().split())
    return collapsed.startswith(_BANNED_SCHEMES)
