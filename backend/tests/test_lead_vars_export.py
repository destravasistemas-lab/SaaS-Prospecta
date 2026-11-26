"""
Variáveis por contato no disparo (lead_vars), colunas extras do CSV importado
e exportação dos leads em CSV.
"""
import csv
import io
import json
import uuid

import pytest
from sqlalchemy import select

from app.models.lead import Lead
from app.services import lead_vars


def _lead(**kw) -> Lead:
    base = dict(id=str(uuid.uuid4()), account_id="acc", instagram_handle="5583999998888",
                phone="5583999998888", source="manual", status="new")
    return Lead(**{**base, **kw})


def test_resolve_lead_fields_and_custom_columns():
    lead = _lead(name="Maria Souza", email="m@x.com",
                 metadata_json=json.dumps({"campos": {"cidade": "João Pessoa", "nome_da_loja": "Bella"}}))
    values, missing = lead_vars.resolve(
        ["{{primeiro_nome}}", "Loja {{Nome_da_Loja}} em {{ cidade }}", "texto fixo"], lead,
    )
    assert values == ["Maria", "Loja Bella em João Pessoa", "texto fixo"]
    assert missing == set()


def test_resolve_reports_missing_and_uses_default():
    lead = _lead(name="5583999998888")  # importado sem nome: o telefone não é nome
    values, missing = lead_vars.resolve(["{{primeiro_nome|tudo bem}}", "{{cidade}}"], lead)
    assert values[0] == "tudo bem"
    assert missing == {"cidade"}


def test_resolve_cleans_what_meta_rejects():
    lead = _lead(name="Ana", metadata_json=json.dumps({"campos": {"obs": "linha 1\nlinha\t2     fim"}}))
    values, _ = lead_vars.resolve(["{{obs}}"], lead)
    assert values == ["linha 1 linha 2 fim"]


def test_field_key_normalizes_headers():
    assert lead_vars.field_key("Nome da Loja") == "nome_da_loja"
    assert lead_vars.field_key("  Cidade/UF ") == "cidade_uf"
    assert lead_vars.field_key("Endereço") == "endereco"


@pytest.mark.asyncio
async def test_csv_import_keeps_extra_columns_as_fields(client, db_session, make_user):
    tid, headers = await make_user()
    content = "nome;telefone;email;Cidade;Nome da Loja\nJoão Lima;(83) 98888-7777;J@X.COM;Patos;Casa Azul\n"
    resp = await client.post("/api/v1/leads/import", headers=headers,
                             files={"file": ("l.csv", content.encode(), "text/csv")})
    assert resp.json()["created"] == 1

    lead = (await db_session.execute(select(Lead).where(Lead.account_id == tid))).scalar_one()
    assert lead.email == "j@x.com"
    assert lead_vars.custom_fields(lead) == {"cidade": "Patos", "nome_da_loja": "Casa Azul"}

    fields = (await client.get("/api/v1/whatsapp/broadcast/fields", headers=headers)).json()
    assert "primeiro_nome" in fields["base"]
    assert fields["custom"] == ["cidade", "nome_da_loja"]


def _rows(resp) -> list[list[str]]:
    assert resp.status_code == 200
    assert resp.headers["content-type"].startswith("text/csv")
    assert "attachment" in resp.headers["content-disposition"]
    text = resp.content.decode("utf-8")
    assert text.startswith("﻿")
    return list(csv.reader(io.StringIO(text[1:]), delimiter=";"))


@pytest.mark.asyncio
async def test_export_interested_leads(client, db_session, make_user):
    tid, headers = await make_user()
    other_tid, _ = await make_user()
    db_session.add_all([
        _lead(account_id=tid, name="Quente", phone="5583900000001", score_label="hot", score=80,
              metadata_json=json.dumps({"campos": {"cidade": "Recife"}})),
        _lead(account_id=tid, name="Fechou", phone="5583900000002", status="converted"),
        _lead(account_id=tid, name="Qualificado", phone="5583900000003", status="qualified", score_label="warm"),
        _lead(account_id=tid, name="Frio", phone="5583900000004", score_label="cold"),
        _lead(account_id=other_tid, name="Outro tenant", phone="5583900000005", score_label="hot"),
    ])
    await db_session.flush()

    rows = _rows(await client.get("/api/v1/leads/export", params={"interested": "true"}, headers=headers))
    header, body = rows[0], rows[1:]
    assert header[0] == "Nome" and header[-1] == "cidade"
    assert sorted(r[0] for r in body) == ["Fechou", "Qualificado", "Quente"]
    quente = next(r for r in body if r[0] == "Quente")
    assert quente[1] == "55 (83) 90000-0001"
    assert quente[5] == "Quente" and quente[-1] == "Recife"

    rows = _rows(await client.get("/api/v1/leads/export",
                                  params={"status": "converted,qualified"}, headers=headers))
    assert sorted(r[0] for r in rows[1:]) == ["Fechou", "Qualificado"]

    bad = await client.get("/api/v1/leads/export", params={"status": "xyz"}, headers=headers)
    assert bad.status_code == 422


@pytest.mark.asyncio
async def test_export_neutralizes_spreadsheet_formulas(client, db_session, make_user):
    tid, headers = await make_user()
    db_session.add(_lead(account_id=tid, name="=HYPERLINK(\"http://x\")", phone="5583900000009"))
    await db_session.flush()

    rows = _rows(await client.get("/api/v1/leads/export", headers=headers))
    assert rows[1][0].startswith("'=")
