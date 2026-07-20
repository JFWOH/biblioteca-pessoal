"""Ponte JS↔Python para capturar a seleção de texto no caminho EPUB.

Contexto (débito 3.4 / rodada B3): o Word Wise (definição rápida de um termo
selecionado) só existia no caminho PDF, onde a seleção é geométrica sobre um
QLabel. O EPUB renderiza num ``QWebEngineView`` (Chromium em processo
separado), onde os eventos de mouse do Qt no widget NÃO chegam de forma
confiável ao ``eventFilter`` do ReaderView. O caminho robusto — validado no
spike ``tools/spike_epub_selection.py`` — é detectar o fim da seleção pelo
evento ``mouseup`` do próprio DOM (roda no renderer, sempre dispara) e enviar
o texto + retângulo da seleção ao Python via ``QWebChannel``.

ADR-006: isto é GUI (JS/bridge vivem em ``src/gui``); o core segue puro.
ADR-005: se o JS falhar (canal indisponível, seleção vazia), o resultado é
simplesmente "nenhum popover" — nunca um crash.

Este módulo importa apenas ``PyQt6.QtCore`` (NÃO ``QtWebEngineWidgets``), então
pode ser importado e testado na suíte normal — diferente de ``reader_view``.
"""

from PyQt6.QtCore import QObject, pyqtSignal, pyqtSlot


# JS injetado em TODA página EPUB/HTML após o ``loadFinished`` (o ``setHtml`` de
# cada virada de página cria um documento novo, apagando listeners anteriores).
# É código CONFIÁVEL do leitor — não vem do livro (o HTML do livro é sanitizado
# por ``sanitize_book_html`` antes do ``setHtml``). A guarda ``__epubWW`` evita
# fiar duas vezes caso ``loadFinished`` dispare mais de uma vez para o mesmo doc.
#
# O nome do objeto registrado ("epubBridge") e do slot ("on_selection_end")
# precisam bater com ``EpubSelectionBridge`` e o ``registerObject`` no ReaderView.
EPUB_SELECTION_JS = r"""
(function () {
  if (window.__epubWW) { return; }
  window.__epubWW = true;

  function wireMouseUp(bridge) {
    document.addEventListener('mouseup', function () {
      // Adiado um tick: no mouseup a seleção do DOM já está estável.
      window.setTimeout(function () {
        try {
          var sel = window.getSelection();
          var text = sel ? sel.toString() : '';
          var rect = '';
          if (sel && sel.rangeCount && text) {
            var r = sel.getRangeAt(0).getBoundingClientRect();
            rect = JSON.stringify({
              x: r.x, y: r.y, w: r.width, h: r.height,
              bottom: r.bottom, right: r.right
            });
          }
          bridge.on_selection_end(text || '', rect);
        } catch (e) { /* ADR-005: falha silenciosa, sem popover */ }
      }, 0);
    });
  }

  function connect() {
    try {
      new QWebChannel(qt.webChannelTransport, function (channel) {
        var bridge = channel.objects.epubBridge;
        if (bridge) { wireMouseUp(bridge); }
      });
    } catch (e) { /* canal indisponível — degrada sem popover */ }
  }

  if (typeof QWebChannel !== 'undefined') {
    connect();
  } else {
    var s = document.createElement('script');
    s.src = 'qrc:///qtwebchannel/qwebchannel.js';
    s.onload = connect;
    s.onerror = function () { /* sem qwebchannel.js: degrada sem popover */ };
    document.head.appendChild(s);
  }
})();
"""


class EpubSelectionBridge(QObject):
    """Objeto exposto ao JS da página EPUB via ``QWebChannel``.

    O JS chama :meth:`on_selection_end` a cada ``mouseup`` com o texto
    selecionado e o retângulo (JSON, coords CSS relativas ao viewport) ou ``""``
    quando a seleção está vazia. O ReaderView escuta :attr:`selection_ended`.
    """

    # (texto_selecionado, rect_json)  — rect_json == "" quando não há seleção.
    selection_ended = pyqtSignal(str, str)

    @pyqtSlot(str, str)
    def on_selection_end(self, text: str, rect_json: str) -> None:
        self.selection_ended.emit(text or "", rect_json or "")
