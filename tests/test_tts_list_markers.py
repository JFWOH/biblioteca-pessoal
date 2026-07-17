"""Marcadores de lista na narração (sintoma real, teste do usuário 2026-07-17).

A extração de PDF entrega itens de lista como ``* Texto`` e o motor de voz
verbalizava o símbolo: "asterisco Texto". ``strip_list_markers`` remove os
marcadores ANTES do colapso de quebras de linha, dá a cada item a pausa de fim
de frase e pontua a linha-introdução da lista; asteriscos residuais (ênfase
markdown, marcador de nota) são removidos em qualquer posição.
"""
from src.core.tts.text_preprocess import strip_list_markers
from src.core.tts.text_preprocessor import TTSTextPreprocessor

# Reproduz a página do print do usuário ("In This Chapter" + itens com "*").
_PAGINA_REAL = (
    "In This Chapter\n"
    "* Discovering Claude's superpowers (and why they matter to you)\n"
    "* Understanding the boundaries: what Claude won't and can't do\n"
    "* Learning to spot and handle AI hallucinations like a pro\n"
    "You wouldn't use a hammer to paint a portrait.\n"
)


class TestStripListMarkers:
    def test_asterisco_nao_sobrevive_no_sintoma_real(self):
        out = strip_list_markers(_PAGINA_REAL)
        assert "*" not in out
        # Cada item vira sentença própria (pausa de fim de frase).
        assert "to you)." in out
        assert "can't do." in out
        assert "like a pro." in out

    def test_linha_introducao_da_lista_ganha_pausa(self):
        out = strip_list_markers(_PAGINA_REAL)
        # Sem o ponto, "In This Chapter" seria colado ao primeiro item.
        assert "In This Chapter." in out

    def test_bullets_unicode_tambem_sao_removidos(self):
        out = strip_list_markers("Temas\n• Primeiro item\n• Segundo item\n")
        assert "•" not in out
        assert "Primeiro item." in out
        assert "Segundo item." in out

    def test_traco_como_marcador_exige_espaco(self):
        out = strip_list_markers("Lista\n- Item com traço\n")
        assert "Item com traço." in out
        assert "\n- " not in out

    def test_palavra_hifenizada_no_inicio_da_linha_fica_intacta(self):
        texto = "contexto anterior\n-palavra quebrada pelo OCR\n"
        assert "-palavra" in strip_list_markers(texto)

    def test_item_com_continuacao_nao_ganha_ponto_no_meio(self):
        texto = (
            "Capítulo\n"
            "* Um item comprido que continua\n"
            "na linha seguinte sem marcador\n"
            "* Outro item\n"
        )
        out = strip_list_markers(texto)
        # A 1ª linha física do item quebrado NÃO pode ganhar ponto no meio.
        assert "que continua." not in out
        assert "Outro item." in out

    def test_asterisco_de_enfase_e_nota_removidos_em_qualquer_posicao(self):
        out = strip_list_markers("Isto é *importante* e notório* demais.")
        assert "*" not in out
        assert "importante" in out and "notório" in out

    def test_item_ja_pontuado_nao_ganha_ponto_duplo(self):
        out = strip_list_markers("Lista\n* Item já pontuado.\n")
        assert "Item já pontuado." in out
        assert "pontuado.." not in out

    def test_idempotente(self):
        uma = strip_list_markers(_PAGINA_REAL)
        assert strip_list_markers(uma) == uma

    def test_entrada_vazia_segura(self):
        assert strip_list_markers("") == ""
        assert strip_list_markers("sem lista nenhuma") == "sem lista nenhuma"


class TestPipelineCompleto:
    def test_prepare_for_speech_nao_deixa_asterisco(self):
        pre = TTSTextPreprocessor(language="pt-BR")
        out = pre.prepare_for_speech(_PAGINA_REAL)
        assert "*" not in out
        # As pausas dos itens sobrevivem ao restante do pipeline.
        assert "like a pro." in out
