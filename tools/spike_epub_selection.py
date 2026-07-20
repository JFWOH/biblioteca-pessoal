"""SPIKE B3 — viabilidade do Word Wise (e seleção) no caminho EPUB.

Prova empírica, offscreen, dos 3 pilares para capturar a seleção de texto num
``QWebEngineView`` (onde o EPUB é renderizado). Rode com o venv do projeto:

    set QT_QPA_PLATFORM=offscreen
    venv\\Scripts\\python.exe tools\\spike_epub_selection.py

RESULTADOS OBSERVADOS (Qt 6 / PyQt6, Windows, offscreen — 2026-07):

 (a) window.getSelection().toString() via runJavaScript devolve a seleção.
     -> OK. ~117 ms na 1a chamada (warmup do JS + criação da seleção), ~1.5 ms
        em re-leituras. É o MESMO call que já roda em _on_epub_context_menu.

 (b) getRangeAt(0).getBoundingClientRect() -> coords do viewport (CSS px), já
     relativas ao scroll. Conversão p/ widget:  coord_widget = css * zoomFactor.
     -> OK. Verificado: rect CSS é INVARIANTE sob zoom (o zoom aparece só no
        fator de composição do widget) e ACOMPANHA o scroll (viewport-relative).
        Quando a seleção rola para fora da vista, y fica negativo -> clampar/ocultar.

 (c) "seleção terminou":
     - QWebEnginePage.selectionChanged: NÃO dispara offscreen (nem p/ Range JS,
       nem p/ triggerAction SelectAll/Unselect). page.selectedText()/hasSelection()
       refletem a seleção, mas o SINAL é inconfiável -> NÃO usar como gatilho.
     - mouseup do DOM -> QWebChannel -> Python: OK. Entrega texto + rect ao slot
       Python (~69 ms). O mouseup do DOM roda no renderer e SEMPRE dispara,
       independente do processo separado do Chromium — este é o caminho robusto.

VEREDITO: VIÁVEL COM RESSALVAS. Gatilho = mouseup(JS)->QWebChannel; texto =
getSelection().toString(); posição = getBoundingClientRect * zoomFactor. Ressalva
principal: validação end-to-end ON-SCREEN (posicionamento do popover, foco no
processo separado) fica pendente — offscreen tem innerWidth/innerHeight = 0.
"""
import os

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")
os.environ.setdefault("QTWEBENGINE_DISABLE_SANDBOX", "1")
os.environ.setdefault("QTWEBENGINE_CHROMIUM_FLAGS",
                      "--disable-gpu --no-sandbox --disable-software-rasterizer")

import sys
import json
import time

from PyQt6.QtWidgets import QApplication
from PyQt6.QtWebEngineWidgets import QWebEngineView
from PyQt6.QtCore import QEventLoop, QTimer, QObject, pyqtSlot
from PyQt6.QtWebChannel import QWebChannel

HTML = """<!DOCTYPE html>
<html><head><meta charset="utf-8"><style>
  body { margin:0; padding:20px; font-family: serif; font-size:16px; line-height:1.6; }
  #tall { height: 1500px; }
</style></head>
<body><div id="tall">
  <p>Antes do alvo. Texto de enchimento para empurrar o conteudo.</p>
  <p id="target">supercalifragilistic epialidocious wordwise</p>
  <p>Depois do alvo, mais texto para permitir rolagem vertical real.</p>
</div></body></html>"""

SELECT_JS = """(function(){
  var el=document.getElementById('target');
  var range=document.createRange(); range.selectNodeContents(el);
  var sel=window.getSelection(); sel.removeAllRanges(); sel.addRange(range);
  return window.getSelection().toString();
})();"""

RECT_JS = """(function(){
  var sel=window.getSelection(); if(!sel.rangeCount) return null;
  var r=sel.getRangeAt(0).getBoundingClientRect();
  return JSON.stringify({x:r.x,y:r.y,w:r.width,h:r.height,bottom:r.bottom,
    scrollY:window.scrollY,dpr:window.devicePixelRatio});
})();"""

WIRE_JS = """(function(){
  var s=document.createElement('script');
  s.src='qrc:///qtwebchannel/qwebchannel.js';
  s.onload=function(){
    new QWebChannel(qt.webChannelTransport,function(ch){
      var b=ch.objects.epubBridge;
      document.addEventListener('mouseup',function(){
        var sel=window.getSelection();
        var t=sel.toString();
        var rj='';
        if(sel.rangeCount){
          var r=sel.getRangeAt(0).getBoundingClientRect();
          rj=JSON.stringify({x:r.x,bottom:r.bottom});
        }
        if(b){ b.on_selection_end(t,rj); }
      });
    });
  };
  document.head.appendChild(s);
})();"""

FIRE_MOUSEUP_JS = """(function(){
  var el=document.getElementById('target');
  var r=el.getBoundingClientRect();
  el.dispatchEvent(new MouseEvent('mouseup',{bubbles:true,clientX:r.x+5,clientY:r.y+5}));
})();"""


def spin(ms):
    loop = QEventLoop()
    QTimer.singleShot(ms, loop.quit)
    loop.exec()


def run_js(page, script, timeout_ms=3000):
    res = {"v": None, "done": False}
    loop = QEventLoop()

    def cb(v):
        res["v"] = v
        res["done"] = True
        loop.quit()

    t0 = time.perf_counter()
    QTimer.singleShot(timeout_ms, loop.quit)
    page.runJavaScript(script, cb)
    loop.exec()
    return res["v"], (time.perf_counter() - t0) * 1000.0, res["done"]


class Bridge(QObject):
    def __init__(self):
        super().__init__()
        self.last = None
        self.n = 0

    @pyqtSlot(str, str)
    def on_selection_end(self, text, rect_json):
        self.n += 1
        self.last = (text, rect_json)


def main():
    app = QApplication(sys.argv)
    view = QWebEngineView()
    view.resize(800, 600)
    page = view.page()

    lf = QEventLoop()
    page.loadFinished.connect(lambda ok: lf.quit())
    page.setHtml(HTML)
    QTimer.singleShot(8000, lf.quit)
    lf.exec()
    spin(200)
    report = {}

    # (a) texto da seleção
    val, dt, done = run_js(page, SELECT_JS)
    report["a_selection_text"] = val
    report["a_latency_ms"] = round(dt, 2)
    print(f"(a) getSelection().toString() => {val!r}  ({dt:.1f} ms, done={done})")

    # (b) posição — zoom 1.0, zoom 1.5, e com scroll
    def measure(label):
        raw, _ms, _ = run_js(page, RECT_JS)
        d = json.loads(raw) if raw else None
        zf = page.zoomFactor()
        if d:
            print(f"(b:{label}) zoom={zf:.2f} css=({d['x']:.0f},{d['y']:.0f}) "
                  f"scrollY={d['scrollY']:.0f} -> widget=({d['x'] * zf:.0f},{d['y'] * zf:.0f})")
        return d

    d1 = measure("zoom1")
    page.setZoomFactor(1.5)
    spin(150)
    d2 = measure("zoom1.5")
    page.setZoomFactor(1.0)
    spin(100)
    run_js(page, "window.scrollTo(0,400);")
    spin(150)
    d3 = measure("scroll400")
    report["b_css_invariant_under_zoom"] = bool(
        d1 and d2 and abs(d1["y"] - d2["y"]) < 1.0)
    report["b_follows_scroll"] = bool(
        d1 and d3 and abs((d1["y"] - d3["y"]) - 400.0) < 30.0)

    # (c1) selectionChanged (esperado: NÃO dispara offscreen)
    run_js(page, "window.scrollTo(0,0);")
    spin(100)
    sc = {"n": 0}
    page.selectionChanged.connect(lambda: sc.__setitem__("n", sc["n"] + 1))
    run_js(page, "window.getSelection().removeAllRanges();")
    spin(80)
    run_js(page, SELECT_JS)
    spin(120)
    report["c1_selectionChanged_fired"] = sc["n"] > 0
    report["c1_selectedText_qt_side"] = page.selectedText()
    print(f"(c1) selectionChanged fired={sc['n'] > 0}  "
          f"page.selectedText()={page.selectedText()!r}")

    # (c2) mouseup -> QWebChannel -> Python
    bridge = Bridge()
    channel = QWebChannel()
    channel.registerObject("epubBridge", bridge)
    page.setWebChannel(channel)
    run_js(page, WIRE_JS)
    spin(400)
    run_js(page, SELECT_JS)
    spin(80)
    run_js(page, FIRE_MOUSEUP_JS)
    spin(300)
    report["c2_bridge_received"] = bridge.n > 0
    report["c2_bridge_payload"] = bridge.last
    print(f"(c2) mouseup->QWebChannel received={bridge.n > 0} payload={bridge.last!r}")

    print("\n=== JSON REPORT ===")
    print(json.dumps(report, ensure_ascii=False, indent=2))
    QTimer.singleShot(50, app.quit)
    app.exec()


if __name__ == "__main__":
    main()
