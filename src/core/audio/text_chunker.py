import re

def clean_reference_markers_for_tts(text: str) -> str:
    """Remove marcadores de referência e notas de rodapé numéricos/sobrescritos.
    
    Preserva expoentes e potências matemáticos legítimos como m², m³, E=mc², x², y².
    """
    if not text:
        return ""

    # 1. Proteger expressões e unidades matemáticas legítimas usando placeholders
    protected = {}
    def protect(match):
        placeholder = f"__MATH_UNIT_{len(protected)}__"
        protected[placeholder] = match.group(0)
        return placeholder

    # Regex conservadora para casar m², m³, cm², cm³, km², km³, mm², mm³, dm², dm³, x², y², z², a², b², c², mc²
    unit_pattern = r'(?i)\b(m|cm|km|mm|dm|x|y|z|a|b|c|mc)[²³]\b'
    text = re.sub(unit_pattern, protect, text)

    # 2. Remover tags HTML de referência <sup>...</sup>
    text = re.sub(r'<sup\b[^>]*>.*?</sup>', '', text, flags=re.IGNORECASE)

    # 3. Remover sobrescritos numéricos após pontuação: 'texto.² Próximo' -> 'texto. Próximo'
    # Aceita dígitos sobrescritos: ¹²³⁴⁵⁶⁷⁸⁹⁰
    text = re.sub(r'(?<!\d)([.!?;:,])\s*[¹²³⁴⁵⁶⁷⁸⁹⁰]+(?=\s|$)', r'\1', text)

    # 3b. Remover dígitos normais de referência após pontuação (ex: 'importantes.2 Enriquecer')
    # Protegido por (?<!\d) e exigindo espaço + letra maiúscula ou fim do texto/linha/parágrafo
    text = re.sub(r'(?<!\d)([.!?;:,])\s*\d{1,3}(?=\s+[A-ZÀ-Ú]|\s*$)', r'\1', text)

    # 4. Remover sobrescritos numéricos antes de pontuação: 'texto².' -> 'texto.'
    text = re.sub(r'(?<=\w)[¹²³⁴⁵⁶⁷⁸⁹⁰]+(?=[.!?;:,])', '', text)

    # 5. Remover citações em colchetes após pontuação: 'texto.[2] Próximo' -> 'texto. Próximo'
    # Suporta múltiplos colchetes adjacentes como [2][3]
    text = re.sub(r'(?<!\d)([.!?;:,])(\s*\[\d{1,4}\])+(?=\s|$)', r'\1', text)

    # 6. Restaurar expressões matemáticas e unidades protegidas
    for placeholder, original in protected.items():
        text = text.replace(placeholder, original)

    return text


def clean_text_for_tts(text: str) -> str:
    """Limpa o texto removendo imperfeições sintáticas comuns de extração de PDF.
    
    Aplicações:
    - Remove marcadores de referência e notas de rodapé numéricos/sobrescritos.
    - Remove hifens artificiais de quebra de linha de PDFs (ex: 'com-\nputador' -> 'computador').
    - Normaliza quebras de linha únicas dentro de parágrafos.
    - Preserva quebras de parágrafo reais (representadas por duplas quebras de linha '\n\n').
    - Normaliza múltiplos espaços consecutivos em branco.
    - Preserva hifens semânticos (ex: 'segunda-feira', 'e-mail').
    """
    if not text:
        return ""

    # Limpeza de marcadores de referência e rodapé
    text = clean_reference_markers_for_tts(text)

    # 1. Remover hifens artificiais de quebra de linha de PDFs
    # Captura hifens precedidos por caractere alfanumérico e seguidos por quebra de linha
    # Ex: 'com-\nputador' ou 'com- \n putador'
    text = re.sub(r'(?<=\w)-\s*\n\s*(?=\w)', '', text)

    # 2. Dividir por parágrafos para normalizar quebras internas
    paragraphs = text.split("\n\n")
    cleaned_paragraphs = []
    
    for p in paragraphs:
        # Substitui quebras de linha simples por espaço
        p_clean = p.replace("\n", " ")
        # Normaliza múltiplos espaços para um espaço simples
        p_clean = re.sub(r'\s+', ' ', p_clean).strip()
        if p_clean:
            cleaned_paragraphs.append(p_clean)
            
    return "\n\n".join(cleaned_paragraphs)


def split_text_for_tts(text: str, max_chars: int = 600) -> list[str]:
    """Divide o texto limpo em blocos (chunks) respeitando limites semânticos.
    
    Regras:
    - Limpa o texto usando clean_text_for_tts.
    - Garante que nenhum bloco ultrapasse max_chars (para controle ágil e stop de baixa latência).
    - Preserva a ordem original do texto.
    - Tenta manter parágrafos intactos se couberem em max_chars.
    - Caso ultrapassem max_chars, divide em frases. Se as frases ultrapassarem, divide em palavras.
    - Nunca retorna blocos vazios.
    """
    cleaned = clean_text_for_tts(text)
    if not cleaned.strip():
        return []

    paragraphs = cleaned.split("\n\n")
    chunks = []

    for p in paragraphs:
        p_strip = p.strip()
        if not p_strip:
            continue
        
        if len(p_strip) <= max_chars:
            chunks.append(p_strip)
        else:
            # Parágrafo muito grande: quebra em sentenças e reagrupa até max_chars
            sentences = re.split(r'(?<=[.!?])\s+', p_strip)
            current_sentence_chunk = ""
            for s in sentences:
                s_strip = s.strip()
                if not s_strip:
                    continue
                
                if len(s_strip) <= max_chars:
                    if not current_sentence_chunk:
                        current_sentence_chunk = s_strip
                    elif len(current_sentence_chunk) + 1 + len(s_strip) <= max_chars:
                        current_sentence_chunk += " " + s_strip
                    else:
                        chunks.append(current_sentence_chunk)
                        current_sentence_chunk = s_strip
                else:
                    # Sentença excede max_chars: descarrega buffer e quebra por palavras
                    if current_sentence_chunk:
                        chunks.append(current_sentence_chunk)
                        current_sentence_chunk = ""
                    
                    words = s_strip.split(" ")
                    current_word_chunk = ""
                    for w in words:
                        w_strip = w.strip()
                        if not w_strip:
                            continue
                        
                        if len(w_strip) <= max_chars:
                            if not current_word_chunk:
                                current_word_chunk = w_strip
                            elif len(current_word_chunk) + 1 + len(w_strip) <= max_chars:
                                current_word_chunk += " " + w_strip
                            else:
                                chunks.append(current_word_chunk)
                                current_word_chunk = w_strip
                        else:
                            # Palavra individual excede max_chars: descarrega buffer e fatia
                            if current_word_chunk:
                                chunks.append(current_word_chunk)
                                current_word_chunk = ""
                            
                            start = 0
                            while start < len(w_strip):
                                slice_str = w_strip[start:start + max_chars]
                                if slice_str:
                                    chunks.append(slice_str)
                                start += max_chars
                    
                    if current_word_chunk:
                        chunks.append(current_word_chunk)
            
            if current_sentence_chunk:
                chunks.append(current_sentence_chunk)

    return chunks
