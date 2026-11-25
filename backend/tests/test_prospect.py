"""
Prospecção por CNPJ: busca, Pix, entrega, CSV, leads e a regra de não repetir CNPJ.
Google Maps: só consulta, com limite diário.
"""
from unittest.mock import AsyncMock, patch

import pytest
from sqlalchemy import select

from app.core.config import settings
from app.models.lead import Lead
from app.models.prospect import (
    CnpjCnae, CnpjCompany, CnpjImportInfo, CnpjMunicipio, ProspectDelivered, ProspectOrder,
)

CNAE = "8630504"  # odontologia
CITY = "2051"


async def _base(db_session, n=6, city=CITY):
    if not await db_session.get(CnpjCnae, CNAE):
        db_session.add(CnpjCnae(code=CNAE, description="Atividade odontológica", search="atividade odontologica"))
    if not await db_session.get(CnpjMunicipio, city):
        db_session.add(CnpjMunicipio(code=city, name="Joao Pessoa", uf="PB", search="joao pessoa"))
    if not await db_session.get(CnpjImportInfo, 1):
        db_session.add(CnpjImportInfo(id=1, reference_month="2026-11", ufs="PB", total=n))
    for i in range(n):
        db_session.add(CnpjCompany(
            cnpj=f"{city}{i:010d}", razao_social=f"CLINICA {i} LTDA", nome_fantasia=f"Sorriso {i}",
            cnae=CNAE, uf="PB", municipio_code=city, bairro="MANAIRA" if i % 2 else "TAMBAU",
            endereco="RUA A, 10", cep="58000000", telefone1=f"55833333{i:04d}" if i != 5 else None,
            email=f"c{i}@ex.com", porte="01", mei=(i == 4), abertura="20200115",
        ))
    await db_session.flush()


def _asaas():
    return (
        patch("app.routes.prospect.asaas_service.create_customer", new_callable=AsyncMock, return_value={"id": "cus_1"}),
        patch("app.routes.prospect.asaas_service.create_payment", new_callable=AsyncMock,
              return_value={"id": "pay_1", "invoiceUrl": "https://asaas/i/1"}),
        patch("app.routes.prospect.asaas_service.get_pix_qr", new_callable=AsyncMock,
              return_value={"payload": "000201PIX", "encodedImage": "iVBOR"}),
    )


SEARCH = {"cnae": CNAE, "municipio_code": CITY}
BUYER = {"buyer_name": "Clínica Teste", "buyer_document": "123.456.789-09"}


@pytest.mark.asyncio
async def test_quote_counts_prices_and_masks_preview(client, db_session, make_user, monkeypatch):
    monkeypatch.setattr(settings, "prospect_price_per_contact", 0.5)
    monkeypatch.setattr(settings, "prospect_min_order", 2.0)
    _, headers = await make_user()
    await _base(db_session)

    r = (await client.post("/api/v1/prospect/quote", json=SEARCH, headers=headers)).json()
    assert r["available"] == 5  # a empresa sem telefone fica de fora por padrão
    assert r["amount"] == 2.5
    p = r["preview"][0]
    assert "•" in p["phone"] and p["phone"].startswith("(83)") and "@ex.com" in p["email"]

    r = (await client.post("/api/v1/prospect/quote", json={**SEARCH, "exclude_mei": True, "quantity": 2}, headers=headers)).json()
    assert r["available"] == 4 and r["quantity"] == 2 and r["amount"] == 2.0  # mínimo do pedido

    r = (await client.post("/api/v1/prospect/quote", json={**SEARCH, "bairro": "manaira"}, headers=headers)).json()
    assert r["available"] == 2


@pytest.mark.asyncio
async def test_pix_order_then_paid_list_never_comes_back(client, db_session, make_user, monkeypatch):
    monkeypatch.setattr(settings, "asaas_api_key", "k")
    tid, headers = await make_user()
    await _base(db_session)

    a, b, c = _asaas()
    with a, b as pay, c:
        r = await client.post("/api/v1/prospect/orders", json={**SEARCH, **BUYER, "quantity": 3}, headers=headers)
    assert r.status_code == 201
    order = r.json()
    assert order["status"] == "pending" and order["quantity"] == 3 and order["pix_payload"] == "000201PIX"
    assert pay.call_args.kwargs["billing_type"] == "PIX"

    # Reservados: a busca seguinte já não mostra esses 3
    q = (await client.post("/api/v1/prospect/quote", json=SEARCH, headers=headers)).json()
    assert q["available"] == 2

    # CSV bloqueado até pagar
    assert (await client.get(f"/api/v1/prospect/orders/{order['id']}/csv", headers=headers)).status_code == 402

    # Webhook do Asaas confirma o pagamento
    monkeypatch.setattr(settings, "asaas_webhook_token", "tok")
    w = await client.post("/api/v1/payments/webhook/asaas", json={"event": "PAYMENT_RECEIVED", "payment": {"id": "pay_1"}},
                          headers={"asaas-access-token": "tok"})
    assert w.status_code == 200
    st = (await client.get(f"/api/v1/prospect/orders/{order['id']}", headers=headers)).json()
    assert st["status"] == "paid" and "pix_payload" not in st
    delivered = (await db_session.execute(select(ProspectDelivered).where(ProspectDelivered.account_id == tid))).scalars().all()
    assert len(delivered) == 3

    csv = await client.get(f"/api/v1/prospect/orders/{order['id']}/csv", headers=headers)
    assert csv.status_code == 200
    lines = csv.content.decode("utf-8-sig").strip().splitlines()
    assert len(lines) == 4 and lines[0].startswith("cnpj;razao_social")
    assert "(83) 3333-0000" in lines[1] and "Atividade odontológica" in lines[1] and "Joao Pessoa" in lines[1]

    # Comprou: na mesma busca só sobram os 2 que ainda não vieram
    q = (await client.post("/api/v1/prospect/quote", json=SEARCH, headers=headers)).json()
    assert q["available"] == 2

    leads = (await client.post(f"/api/v1/prospect/orders/{order['id']}/import-leads", headers=headers)).json()
    assert leads == {"created": 3, "skipped": 0}
    again = (await client.post(f"/api/v1/prospect/orders/{order['id']}/import-leads", headers=headers)).json()
    assert again == {"created": 0, "skipped": 3}
    lead = (await db_session.execute(select(Lead).where(Lead.account_id == tid).limit(1))).scalar_one()
    assert lead.whatsapp_opt_in is False and "prospeccao_cnpj" in lead.metadata_json


@pytest.mark.asyncio
async def test_other_account_is_not_affected_and_cannot_see_orders(client, db_session, make_user, monkeypatch):
    monkeypatch.setattr(settings, "asaas_api_key", "k")
    _, headers_a = await make_user()
    _, headers_b = await make_user()
    await _base(db_session, city="1111")
    search = {"cnae": CNAE, "municipio_code": "1111"}
    a, b, c = _asaas()
    with a, b, c:
        order = (await client.post("/api/v1/prospect/orders", json={**search, **BUYER}, headers=headers_a)).json()
    assert (await client.post("/api/v1/prospect/quote", json=search, headers=headers_b)).json()["available"] == 5
    assert (await client.get(f"/api/v1/prospect/orders/{order['id']}", headers=headers_b)).status_code == 404
    assert (await client.get(f"/api/v1/prospect/orders/{order['id']}/csv", headers=headers_b)).status_code == 404


@pytest.mark.asyncio
async def test_nothing_new_and_invalid_document(client, db_session, make_user, monkeypatch):
    monkeypatch.setattr(settings, "asaas_api_key", "k")
    _, headers = await make_user()
    r = await client.post("/api/v1/prospect/orders", json={**SEARCH, "municipio_code": "9999", **BUYER}, headers=headers)
    assert r.status_code == 409
    r = await client.post("/api/v1/prospect/orders", json={**SEARCH, "buyer_name": "X Y", "buyer_document": "123"}, headers=headers)
    assert r.status_code == 422


@pytest.mark.asyncio
async def test_super_admin_gets_list_free_and_status_endpoint(client, db_session, make_user, monkeypatch):
    _, headers = await make_user()
    from app.models.user import User
    user = (await db_session.execute(select(User).order_by(User.created_at.desc()).limit(1))).scalar_one()
    monkeypatch.setattr(settings, "super_admin_emails", user.username)
    await _base(db_session, city="2222")
    st = (await client.get("/api/v1/prospect/status", headers=headers)).json()
    assert st["cnpj_available"] and st["free"] is True
    r = await client.post("/api/v1/prospect/orders", json={"cnae": CNAE, "municipio_code": "2222", **BUYER}, headers=headers)
    assert r.json()["status"] == "paid" and r.json()["amount"] == 0
    order = await db_session.get(ProspectOrder, r.json()["id"])
    assert order.asaas_payment_id is None


@pytest.mark.asyncio
async def test_cnae_and_city_search(client, db_session, make_user):
    _, headers = await make_user()
    await _base(db_session, n=1, city="3333")
    assert (await client.get("/api/v1/prospect/cnaes?q=Odontológica", headers=headers)).json()[0]["code"] == CNAE
    assert (await client.get("/api/v1/prospect/cnaes?q=8630", headers=headers)).json()[0]["code"] == CNAE
    assert (await client.get("/api/v1/prospect/cities?q=joão", headers=headers)).json()[0]["uf"] == "PB"


class _FakeResp:
    status_code = 200

    def json(self):
        return {"places": [{"id": "p1", "displayName": {"text": "Clínica Sorriso"}, "nationalPhoneNumber": "(83) 3333-0000",
                            "googleMapsUri": "https://maps.google.com/?cid=1", "rating": 4.8}]}


class _FakeClient:
    def __init__(self, *a, **k):
        pass

    async def __aenter__(self):
        return self

    async def __aexit__(self, *a):
        return False

    async def post(self, *a, **k):
        return _FakeResp()


@pytest.mark.asyncio
async def test_places_search_and_daily_limit(client, make_user, monkeypatch):
    _, headers = await make_user()
    assert (await client.get("/api/v1/prospect/places?q=dentista joao pessoa", headers=headers)).status_code == 503
    monkeypatch.setattr(settings, "google_maps_api_key", "g")
    monkeypatch.setattr(settings, "google_maps_searches_per_day", 2)
    with patch("app.routes.prospect.httpx.AsyncClient", _FakeClient):
        r1 = await client.get("/api/v1/prospect/places?q=dentista joao pessoa", headers=headers)
        assert r1.json()["places"][0]["name"] == "Clínica Sorriso"
        assert (await client.get("/api/v1/prospect/places?q=dentista", headers=headers)).status_code == 200
        assert (await client.get("/api/v1/prospect/places?q=dentista", headers=headers)).status_code == 429


def test_import_parser_filters_and_strips_cpf():
    from scripts.import_cnpj import parse_estabelecimento, strip_cpf
    row = ["12345678", "0001", "95", "1", "SORRISO", "02", "", "", "", "", "20200115", "8630504", "8630503,8640205",
           "RUA", "DAS FLORES", "10", "SALA 2", "MANAIRA", "58000000", "PB", "2051", "83", "33330000", "", "", "", "",
           "Contato@Ex.com", "", ""]
    rec = parse_estabelecimento(row, {"PB"})
    assert rec[0] == "12345678000195" and rec[3] == "8630504" and rec[4] == ",8630503,8640205,"
    assert rec[10] == "558333330000" and rec[12] == "contato@ex.com" and rec[8] == "RUA DAS FLORES, 10, SALA 2"
    assert parse_estabelecimento(row, {"PE"}) is None
    inactive = list(row); inactive[5] = "08"
    assert parse_estabelecimento(inactive, {"PB"}) is None
    no_contact = list(row); no_contact[22] = ""; no_contact[27] = ""
    assert parse_estabelecimento(no_contact, {"PB"}) is None
    assert strip_cpf("JOAO DA SILVA 12345678909") == "JOAO DA SILVA"
    assert strip_cpf("CLINICA SORRISO LTDA") == "CLINICA SORRISO LTDA"
