"""Leitor de documentos PDF usando PyMuPDF."""

from pathlib import Path
from src.readers.base_reader import BaseReader, BookOpenError, PageContent, TOCEntry


def _lado_a_lado(pix, pix2) -> tuple[bytes, int, int]:
    """Junta dois pixmaps lado a lado e devolve (PNG, largura, altura).

    ADR-006 (Onda P, ago/2026): esta composição era feita com QImage/QPainter
    DENTRO de ``get_page``, o que fazia ``src/readers/**`` importar PyQt6 —
    violação da fronteira. O resultado é idêntico (fundo branco, página
    esquerda na origem, direita deslocada pela largura da primeira), só que
    agora em PyMuPDF puro: o leitor devolve bytes e quem monta ``QPixmap`` é a
    GUI que consome (``reader_view._render_page``).
    """
    import fitz

    width = pix.width + pix2.width
    height = max(pix.height, pix2.height)
    combinado = fitz.Pixmap(fitz.csRGB, fitz.IRect(0, 0, width, height), False)
    combinado.clear_with(255)  # branco, como o antigo QImage.fill(white)
    pix.set_origin(0, 0)
    combinado.copy(pix, pix.irect)
    pix2.set_origin(pix.width, 0)
    combinado.copy(pix2, pix2.irect)
    return combinado.tobytes("png"), width, height


class PDFReader(BaseReader):
    """Leitor de PDF com renderização de alta qualidade."""

    def __init__(self, filepath: str | Path):
        super().__init__(filepath)
        self._doc = None
        self._zoom = 1.5  # Fator de zoom padrão
        self.is_double_page = False

    def set_double_page(self, active: bool) -> None:
        """Ativa/Desativa o modo de leitura em página dupla."""
        self.is_double_page = active

    @property
    def zoom(self) -> float:
        return self._zoom

    @zoom.setter
    def zoom(self, value: float):
        self._zoom = max(0.5, min(5.0, value))

    def open(self) -> None:
        import fitz
        # Rodada 2 de ajustes de TTS: alguns PDFs têm a árvore estrutural
        # (structure tree, usada por acessibilidade/tagged PDF) malformada e
        # a libmupdf despeja no stderr, por PÁGINA, mensagens como "MuPDF
        # error: format error: No common ancestor in structure tree" — ruído
        # benigno (não impede extração de texto/OCR) que enche o console em
        # lotes grandes (ex.: indexação de centenas de páginas). Suprime só
        # o DISPLAY desses erros não-fatais da lib C; exceções Python reais
        # do fitz continuam sendo propagadas normalmente.
        fitz.TOOLS.mupdf_display_errors(False)
        try:
            self._doc = fitz.open(str(self._filepath))
            self._total_pages = self._doc.page_count
        except Exception as exc:
            self._doc = None
            raise BookOpenError(
                f"Arquivo PDF danificado ou ilegível: {self._filepath.name}"
            ) from exc
        self._is_open = True

    def close(self) -> None:
        if self._doc:
            self._doc.close()
            self._doc = None
        self._is_open = False

    def _apply_highlights(self, page, page_number: int, highlights: list) -> list:
        """Aplica destaques em memória na página; devolve os annots temporários.

        Suporta dois formatos em position_data:
        - "quads": lista de rects (% da página), um por linha de texto —
          destaque que segue o fluxo do texto (frases que começam/terminam
          no meio da linha), como seleção de texto normal;
        - "coords": rect único (% da página) — formato legado/região de imagem.
        """
        import fitz
        import json

        added = []
        for ann in highlights or []:
            if ann.get("page_number") != page_number or ann.get("annotation_type") != "highlight":
                continue
            try:
                pos = json.loads(ann.get("position_data", "{}"))
                rect_obj = page.rect
                pct_rects = pos.get("quads") or (
                    [pos["coords"]] if len(pos.get("coords") or []) == 4 else [])
                rects = [
                    fitz.Rect(rect_obj.width * q[0], rect_obj.height * q[1],
                              rect_obj.width * q[2], rect_obj.height * q[3])
                    for q in pct_rects if len(q) == 4
                ]
                if not rects:
                    continue
                # Um único annot com múltiplos quads: renderização correta
                # linha a linha, sem retângulo cobrindo linhas vizinhas.
                annot = page.add_highlight_annot(rects)

                color_hex = ann.get("highlight_color", "#fbbf24")
                if color_hex.startswith("#"):
                    color_hex = color_hex[1:]
                try:
                    r = int(color_hex[0:2], 16) / 255.0
                    g = int(color_hex[2:4], 16) / 255.0
                    b = int(color_hex[4:6], 16) / 255.0
                except ValueError:
                    r, g, b = 251 / 255.0, 191 / 255.0, 36 / 255.0
                annot.set_colors(stroke=(r, g, b))
                annot.update()
                added.append(annot)
            except Exception as e:
                print(f"[PDFReader] Erro ao aplicar highlight em memória: {e}", flush=True)
        return added

    def get_page(self, page_number: int, highlights: list = None) -> PageContent:
        import fitz

        if not self._doc:
            return PageContent(page_number, self._total_pages, b"", "image")

        page = self._doc[page_number]

        if highlights is None:
            highlights = getattr(self, "highlights", None)

        # ── Aplicação de Destaques em Memória (Página Principal) ──
        added_annots = self._apply_highlights(page, page_number, highlights)
                        
        mat = fitz.Matrix(self._zoom, self._zoom)
        pix = page.get_pixmap(matrix=mat, alpha=False)
        
        # Remove as anotações temporárias da página principal imediatamente
        for annot in added_annots:
            try:
                page.delete_annot(annot)
            except Exception:
                pass

        if self.is_double_page and page_number + 1 < self._total_pages:
            page2 = self._doc[page_number + 1]

            # ── Aplicação de Destaques em Memória (Segunda Página) ──
            added_annots2 = self._apply_highlights(page2, page_number + 1, highlights)

            pix2 = page2.get_pixmap(matrix=mat, alpha=False)
            
            # Remove as anotações temporárias da segunda página imediatamente
            for annot in added_annots2:
                try:
                    page2.delete_annot(annot)
                except Exception:
                    pass
            
            png, width, height = _lado_a_lado(pix, pix2)

            return PageContent(
                page_number=page_number,
                total_pages=self._total_pages,
                content=png,
                content_type="image",
                width=width,
                height=height,
            )
        else:
            return PageContent(
                page_number=page_number,
                total_pages=self._total_pages,
                content=pix.tobytes("png"),
                content_type="image",
                width=pix.width,
                height=pix.height,
            )

    def next_page(self) -> PageContent | None:
        step = 2 if self.is_double_page else 1
        if self._current_page + step < self._total_pages:
            self._current_page += step
            return self.get_page(self._current_page)
        elif self._current_page < self._total_pages - 1:
            self._current_page = self._total_pages - 1
            return self.get_page(self._current_page)
        return None

    def previous_page(self) -> PageContent | None:
        step = 2 if self.is_double_page else 1
        if self._current_page - step >= 0:
            self._current_page -= step
            return self.get_page(self._current_page)
        elif self._current_page > 0:
            self._current_page = 0
            return self.get_page(self._current_page)
        return None

    def get_toc(self) -> list[TOCEntry]:
        if not self._doc:
            return []
        toc = self._doc.get_toc()
        return [
            TOCEntry(title=entry[1], page=entry[2] - 1, level=entry[0] - 1)
            for entry in toc
        ]

    def render_thumbnail(self, page: int, width: int = 110) -> bytes | None:
        """Miniatura PNG da página para o painel de sumário (item 4 UX)."""
        import fitz
        if not self._doc or not (0 <= page < self._total_pages):
            return None
        try:
            p = self._doc[page]
            scale = width / max(p.rect.width, 1)
            pix = p.get_pixmap(matrix=fitz.Matrix(scale, scale), alpha=False)
            return pix.tobytes("png")
        except Exception:
            return None

    def search_text(self, query: str) -> list[dict]:
        if not self._doc:
            return []
        results = []
        for page_num in range(self._total_pages):
            page = self._doc[page_num]
            instances = page.search_for(query)
            for rect in instances:
                results.append({
                    "page": page_num,
                    "rect": [rect.x0, rect.y0, rect.x1, rect.y1],
                    "text": query,
                })
        return results

    def get_page_text(self, page_number: int) -> str:
        """Retorna o texto puro de uma página."""
        if self._doc and 0 <= page_number < self._total_pages:
            return self._doc[page_number].get_text()
        return ""

    def get_page_links(self, page_number: int) -> list[dict]:
        """Retorna links encontrados na página."""
        if not self._doc or page_number >= self._total_pages:
            return []
        page = self._doc[page_number]
        links = []
        for link in page.get_links():
            links.append({
                "kind": link.get("kind"),
                "uri": link.get("uri", ""),
                "page": link.get("page", -1),
                "rect": [link["from"].x0, link["from"].y0,
                         link["from"].x1, link["from"].y1] if "from" in link else [],
            })
        return links

    def get_selection_flow(self, page_number: int,
                           start_pct: tuple[float, float],
                           end_pct: tuple[float, float]) -> dict | None:
        """Seleção que segue o FLUXO do texto entre dois pontos (como seleção
        de texto normal): 1ª linha do ponto inicial até o fim, linhas do meio
        inteiras, última linha até o ponto final.

        Args:
            page_number: página 0-based.
            start_pct/end_pct: pontos (x, y) em % da página (início e fim do
                arrasto do mouse).

        Returns:
            {"text": frase selecionada, "quads": [[x0,y0,x1,y1], ...] em % —
            um rect por linha} ou None se não houver palavras entre os pontos
            (área de imagem → chamador usa o retângulo legado).
        """
        if not self._doc or not (0 <= page_number < self._total_pages):
            return None
        page = self._doc[page_number]
        pw, ph = page.rect.width, page.rect.height
        sx, sy = start_pct[0] * pw, start_pct[1] * ph
        ex, ey = end_pct[0] * pw, end_pct[1] * ph

        # (x0, y0, x1, y1, palavra, block, line, word_no). sort=True pede ao
        # PyMuPDF a ordem de leitura VISUAL (topo→baixo, esq→dir) em vez da
        # ordem de armazenamento no documento — sem isso, um rodapé/cabeçalho
        # guardado em bloco anterior ao corpo da página "vazava" para dentro
        # de qualquer seleção (bug relatado: selecionar um parágrafo traduzia
        # a página inteira, começando pelo número de página do rodapé).
        # Limitação conhecida: PDFs de duas colunas com bandas sobrepostas
        # ainda podem ordenar de forma imperfeita mesmo com sort=True.
        # Cache por página: o feedback ao vivo (item 9) chama este método a
        # cada ~40ms durante o arrasto — extrair as palavras uma vez basta
        # (o documento não muda enquanto aberto).
        cache = getattr(self, "_flow_words_cache", None)
        if cache and cache[0] == page_number:
            words = cache[1]
        else:
            words = page.get_text("words", sort=True)
            self._flow_words_cache = (page_number, words)
        if not words:
            return None

        def first_at_or_after(px: float, py: float) -> int | None:
            """Primeira palavra (ordem de leitura) no ponto ou depois dele."""
            for i, w in enumerate(words):
                if w[3] >= py and (w[1] > py or w[2] >= px):
                    return i
            return None

        def last_at_or_before(px: float, py: float) -> int | None:
            """Última palavra (ordem de leitura) no ponto ou antes dele."""
            found = None
            for i, w in enumerate(words):
                if w[1] <= py and (w[3] < py or w[0] <= px):
                    found = i
            return found

        ia = first_at_or_after(sx, sy)
        ib = last_at_or_before(ex, ey)
        if ia is None or ib is None or ia > ib:
            # Arrasto de baixo para cima / da direita para a esquerda: inverte.
            ia2 = first_at_or_after(ex, ey)
            ib2 = last_at_or_before(sx, sy)
            if ia2 is None or ib2 is None or ia2 > ib2:
                return None
            ia, ib = ia2, ib2

        selected = words[ia:ib + 1]
        # Agrupa por linha (block, line): um rect por linha de texto.
        lines: dict[tuple, list] = {}
        for w in selected:
            lines.setdefault((w[5], w[6]), []).append(w)
        quads = []
        for key in sorted(lines):
            ws = lines[key]
            quads.append([
                min(w[0] for w in ws) / pw, min(w[1] for w in ws) / ph,
                max(w[2] for w in ws) / pw, max(w[3] for w in ws) / ph,
            ])
        text = " ".join(w[4] for w in selected).strip()
        if not text:
            return None
        return {"text": text, "quads": quads}

    def get_text_from_rect(self, page_number: int, rect_pct: tuple[float, float, float, float]) -> str:
        """Extrai texto de um retângulo específico da página.
        rect_pct é (x0, y0, x1, y1) em percentual da largura/altura da página.
        """
        import fitz
        if not self._doc or page_number >= self._total_pages:
            return ""
        page = self._doc[page_number]
        rect_obj = page.rect
        px0, py0, px1, py1 = rect_pct
        
        # Converte o percentual para as coordenadas reais do PyMuPDF
        x0 = rect_obj.width * px0
        y0 = rect_obj.height * py0
        x1 = rect_obj.width * px1
        y1 = rect_obj.height * py1
        
        clip = fitz.Rect(x0, y0, x1, y1)
        return page.get_text("text", clip=clip).strip()
