"""Mensagens da API em espanhol (X-Lang: es), com volta ao português quando falta tradução."""
import pytest

from app.core.i18n import parse_lang, reset_lang, set_lang, t, translate
from app.core.i18n_es import ES


def test_parse_lang_accepts_spanish():
    assert parse_lang("es", None) == "es"
    assert parse_lang(None, "es-AR,es;q=0.9") == "es"
    assert parse_lang("fr", None) == "pt"


def test_spanish_exact_dynamic_and_fallback():
    token = set_lang("es")
    try:
        assert t("Lead não encontrado.", "Lead not found.") == "No se encontró el lead."
        assert translate("Já existe um lead com esse telefone ou e-mail: Ana.") == \
            "Ya existe un lead con ese teléfono o correo: Ana."
        assert translate("Arquivo excede o limite de 10 MB.") == "El archivo supera el límite de 10 MB."
        assert translate("Mensagem nova sem tradução") == "Mensagem nova sem tradução"
    finally:
        reset_lang(token)


def test_every_spanish_entry_keeps_placeholders():
    import re
    for pt, es in ES.items():
        assert sorted(re.findall(r"\{\d+\}", pt)) == sorted(re.findall(r"\{\d+\}", es)), pt


@pytest.mark.asyncio
async def test_http_error_comes_back_in_spanish(client, make_user):
    _, headers = await make_user()
    r = await client.get("/api/v1/leads/nao-existe", headers={**headers, "X-Lang": "es"})
    assert r.status_code == 404
    assert r.json()["detail"] == "No se encontró el lead"
