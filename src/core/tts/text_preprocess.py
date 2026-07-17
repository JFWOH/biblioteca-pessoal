"""Heurística determinística de PAUSA em títulos/subtítulos para TTS.

Sem LLM e sem dependências externas: identifica linhas curtas que funcionam
como título/subtítulo (não terminam em pontuação e estão isoladas por quebras
de linha) e anexa um ponto final. Assim o motor de voz (Kokoro/Piper) dá a
entonação/pausa de fim de frase em vez de colar o título na frase seguinte
(sintoma real: "...a vida real. companheirismo Harold e Erica...").

Roda no núcleo, ANTES do colapso das quebras de linha simples feito por
``TTSTextPreprocessor.normalize_whitespace`` — é por isso que ainda temos a
estrutura de linhas disponível para decidir o que é título.

ADR-006: núcleo puro, sem PyQt6/threads. Função pura e determinística.
"""
from __future__ import annotations

import re

# Linha JÁ pontuada (talvez com aspas/fecho depois): não é título "solto".
_ALREADY_PUNCTUATED = re.compile(r"""[.!?:;,…]["'\)\]»”’]*$""")
# Fim de FRASE da linha anterior (âncora de "início de nova unidade de texto").
_PREV_SENTENCE_END = re.compile(r"""[.!?…]["'\)\]»”’]*$""")
# Ao menos uma letra (unicode; exclui dígitos/símbolos puros).
_HAS_LETTER = re.compile(r"[^\W\d_]", re.UNICODE)

# Marcador de item de lista no INÍCIO da linha. Bullets/asteriscos podem vir
# colados ao texto ("*Nota"); traço exige espaço depois para não confundir com
# hífen de quebra de palavra do OCR ("com-\nputador", tratado noutro passo).
_LIST_BULLET = re.compile(r"^\s*(?:[•●◦▪▸►∙‣]+|\*+)\s*")
_LIST_DASH = re.compile(r"^\s*[-–]\s+")


def strip_list_markers(text: str) -> str:
    """Remove marcadores de lista e dá a cada item a pausa de fim de frase.

    Sintoma real (teste do usuário, 2026-07-17): a extração de PDF entrega
    itens de lista como ``* Texto do item`` e o motor de voz VERBALIZA o
    símbolo — "asterisco Texto do item". O passo antigo (``normalize_lists``)
    não cobria ``*``/``-`` e rodava DEPOIS do colapso de quebras de linha,
    quando as âncoras ``^`` de início de linha já não existiam.

    Esta função roda ANTES do colapso (estrutura de linhas intacta) e:

    * remove o marcador (``• ● ◦ ▪ ▸ ► ∙ ‣ *`` e ``-``/``–`` com espaço);
    * anexa ``.`` ao item que não termina em pontuação — cada item vira uma
      sentença própria (pausa natural) — EXCETO quando a linha seguinte é a
      continuação do próprio item (linha não-vazia sem marcador, caso de
      quebra de linha no meio do item);
    * anexa ``.`` também à linha-introdução da lista (a linha imediatamente
      anterior ao primeiro item, sem pontuação final) — senão ela é colada ao
      primeiro item na narração;
    * por fim, remove asteriscos residuais em QUALQUER posição (ênfase
      markdown ``*palavra*``, marcador de nota ``palavra*``): o símbolo não
      tem leitura útil em prosa.

    Pura, determinística e idempotente (na 2ª passada não há mais marcadores
    nem linhas sem pontuação criadas por ela).
    """
    if not text:
        return text

    lines = text.split("\n")
    n = len(lines)
    is_marker = [bool(_LIST_BULLET.match(ln) and ln.strip()) or bool(_LIST_DASH.match(ln))
                 for ln in lines]

    out: list[str] = []
    for i, ln in enumerate(lines):
        if is_marker[i]:
            s = _LIST_BULLET.sub("", ln, count=1)
            s = _LIST_DASH.sub("", s, count=1)
            s = s.rstrip()
            # Continuação = quebra no MEIO do item: linha seguinte não-vazia,
            # sem marcador e começando em minúscula (meio de frase). Prosa
            # nova após a lista começa com maiúscula e NÃO é continuação —
            # sem isso o último item ficava sem pausa, colado ao parágrafo.
            nxt = lines[i + 1].strip() if i + 1 < n else ""
            has_continuation = bool(
                nxt and not is_marker[i + 1] and nxt[:1].islower()
            )
            if (s and not has_continuation and _HAS_LETTER.search(s)
                    and not _ALREADY_PUNCTUATED.search(s)):
                s += "."
            out.append(s)
        else:
            s = ln
            starts_list = i + 1 < n and is_marker[i + 1]
            stripped = s.strip()
            if (starts_list and stripped and _HAS_LETTER.search(stripped)
                    and not _ALREADY_PUNCTUATED.search(stripped)):
                s = s.rstrip() + "."
            out.append(s)

    return re.sub(r"\*+", "", "\n".join(out))


def mark_heading_pauses(text: str, max_len: int = 64) -> str:
    """Anexa ``.`` a linhas curtas que se comportam como título/subtítulo.

    Uma linha (após ``strip``) é tratada como título quando tem até
    ``max_len`` caracteres, contém alguma letra, NÃO termina em pontuação e
    satisfaz uma das condições de isolamento:

    * está seguida por uma linha em branco (fim de bloco) e começa de forma
      limpa (linha em branco antes, ou a linha anterior termina uma frase);
    * OU vem logo após um fim de frase e começa com letra minúscula — em prosa
      normal uma nova frase começaria com maiúscula, então uma minúscula aqui é
      sinal forte de rótulo/título intercalado (o caso reportado).

    Preserva todo o resto do texto (inclusive quebras de linha e indentação),
    para não perturbar o restante do pipeline de pré-processamento. Determinístico
    e idempotente sobre linhas já pontuadas.
    """
    if not text or "\n" not in text:
        return text

    lines = text.split("\n")
    stripped = [ln.strip() for ln in lines]
    n = len(lines)
    out = list(lines)

    def _prev_nonblank(idx: int) -> str | None:
        j = idx - 1
        while j >= 0 and not stripped[j]:
            j -= 1
        return stripped[j] if j >= 0 else None

    for i, s in enumerate(stripped):
        if not s or len(s) > max_len:
            continue
        if not _HAS_LETTER.search(s):
            continue
        if _ALREADY_PUNCTUATED.search(s):
            continue

        blank_before = i > 0 and not stripped[i - 1]
        blank_after = i < n - 1 and not stripped[i + 1]
        prev_s = _prev_nonblank(i)
        prev_ends_sentence = prev_s is not None and bool(_PREV_SENTENCE_END.search(prev_s))
        before_boundary = blank_before or prev_s is None or prev_ends_sentence

        is_heading = False
        if blank_after and before_boundary:
            # Título/subtítulo bem-formatado: isolado por quebra de parágrafo
            # à frente, começando de forma limpa.
            is_heading = True
        elif prev_ends_sentence and s[:1].islower():
            # Interjeição em minúscula logo após um fim de frase.
            is_heading = True

        if is_heading:
            out[i] = lines[i].rstrip() + "."

    return "\n".join(out)
