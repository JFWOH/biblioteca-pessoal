"""Testes dos helpers puros de observações proativas (Fase 1b)."""
import json

from src.core.proactive_observation import confidence_to_float, obs_dict_from_row


def test_confidence_to_float_known_labels():
    assert confidence_to_float("Alta") == 0.9
    assert confidence_to_float("Média") == 0.6
    assert confidence_to_float("media") == 0.6
    assert confidence_to_float("Baixa") == 0.3


def test_confidence_to_float_unknown_defaults_neutral():
    assert confidence_to_float("") == 0.5
    assert confidence_to_float("qualquer") == 0.5
    assert confidence_to_float(None) == 0.5


def test_obs_dict_from_row_prefers_payload_json():
    obs = {"tipo": "Contexto externo", "confianca": "Alta", "texto": "Conteúdo rico."}
    row = {
        "id": 7,
        "page": 12,
        "kind": "insight",          # diferente do payload, p/ garantir a prioridade do JSON
        "content": "fallback",
        "confidence": 0.9,
        "payload_json": json.dumps(obs, ensure_ascii=False),
    }
    out = obs_dict_from_row(row)
    assert out["tipo"] == "Contexto externo"
    assert out["confianca"] == "Alta"
    assert out["texto"] == "Conteúdo rico."
    assert out["id"] == 7
    assert out["page"] == 12


def test_obs_dict_from_row_fallback_to_columns():
    row = {
        "id": 3,
        "page": 5,
        "kind": "Hipótese interpretativa",
        "content": "Texto da coluna.",
        "confidence": 0.6,
        "payload_json": "",
    }
    out = obs_dict_from_row(row)
    assert out["tipo"] == "Hipótese interpretativa"
    assert out["texto"] == "Texto da coluna."
    assert out["confianca"] == "Média"   # 0.6 → Média
    assert out["id"] == 3
    assert out["page"] == 5


def test_obs_dict_from_row_invalid_json_falls_back():
    row = {
        "id": 1, "page": 2, "kind": "X", "content": "c",
        "confidence": 0.3, "payload_json": "{not valid json",
    }
    out = obs_dict_from_row(row)
    assert out["tipo"] == "X"
    assert out["texto"] == "c"
    assert out["confianca"] == "Baixa"
    assert out["id"] == 1
