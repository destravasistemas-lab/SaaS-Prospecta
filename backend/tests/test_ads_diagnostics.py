"""
Fase 2 dos anúncios: diagnóstico automático e o funil anúncio → lead → venda.
"""
import uuid
from datetime import datetime, timedelta, timezone
from unittest.mock import AsyncMock, patch

import pytest

from app.models.automation import Customer, Sale
from app.models.lead import Lead
from app.services.ads_diagnostics import diagnose

from tests.test_marketing_flow import _ads_setup


def _p(spend=0.0, results=0.0, impressions=0, frequency=0.0, ctr=0.0):
    return {"spend": spend, "results": results, "impressions": impressions, "frequency": frequency, "ctr": ctr,
            "cost_per_result": round(spend / results, 2) if results else 0.0}


def _codes(alerts):
    return {(a["code"], a["campaign_id"]) for a in alerts}


def test_rules():
    campaigns = [{"id": c, "name": c, "effective_status": "ACTIVE"} for c in ("A", "B", "C", "D", "E")]
    perf = {
        "A": {"current": _p(300, 0, 5000, 1.5, 1.2), "previous": _p(100, 2, 4000)},        # gastou sem resultado
        "B": {"current": _p(200, 10, 8000, 3.4, 2.0), "previous": _p(100, 10, 8000)},      # custo dobrou + cansaço
        "C": {"current": _p(100, 20, 9000, 1.2, 0.5), "previous": _p(200, 20, 9000)},      # custo caiu + CTR baixo
        "D": {"current": _p(50, 25, 3000, 1.1, 1.5), "previous": _p(0, 0, 0)},             # melhor custo
    }
    alerts = diagnose(campaigns, perf, days=7)
    codes = _codes(alerts)
    assert ("no_results", "A") in codes
    assert ("cpr_up", "B") in codes and ("fatigue", "B") in codes
    assert ("cpr_down", "C") in codes and ("low_ctr", "C") in codes
    assert ("best", "D") in codes
    assert ("not_delivering", "E") in codes            # ativa e sem impressões
    assert [a["severity"] for a in alerts] == sorted([a["severity"] for a in alerts], key={"warning": 0, "info": 1, "good": 2}.get)
    up = next(a for a in alerts if a["code"] == "cpr_up")
    assert up["values"] == {"cpr": 20.0, "previous": 10.0, "pct": 100.0}


def test_best_only_compares_the_same_kind_of_result():
    campaigns = [{"id": c, "name": c, "effective_status": "PAUSED"} for c in ("L1", "L2", "K1")]
    perf = {
        "L1": {"current": {**_p(100, 10, 5000, 1, 2), "result_label": "Leads"}, "previous": _p()},
        "L2": {"current": {**_p(100, 20, 5000, 1, 2), "result_label": "Leads"}, "previous": _p()},
        "K1": {"current": {**_p(100, 200, 5000, 1, 2), "result_label": "Cliques no link"}, "previous": _p()},
    }
    best = [a for a in diagnose(campaigns, perf, days=30) if a["code"] == "best"]
    assert [(a["campaign_id"], a["values"]["label"]) for a in best] == [("L2", "Leads")]


def test_no_noise_with_little_volume():
    campaigns = [{"id": "A", "name": "A", "effective_status": "PAUSED"}]
    perf = {"A": {"current": _p(30, 0, 500, 4.0, 0.3), "previous": _p(10, 1, 300)}}
    assert diagnose(campaigns, perf, days=30) == []


@pytest.mark.asyncio
async def test_diagnostics_endpoint(client, db_session):
    _, _, headers = await _ads_setup(db_session)
    row = {"spend": "300", "impressions": "5000", "reach": "4000", "frequency": "1.2", "clicks": "50", "ctr": "1",
           "actions": [], "campaign_id": "A"}
    with patch("app.services.ads_service.get_insights", new_callable=AsyncMock, return_value=[row]), \
         patch("app.services.ads_service.get_ad_account", new_callable=AsyncMock, return_value={"account_status": 1}), \
         patch("app.services.ads_service.list_problem_ads", new_callable=AsyncMock, return_value=[]), \
         patch("app.services.ads_service.list_campaigns", new_callable=AsyncMock,
               return_value=[{"id": "A", "name": "Camp A", "effective_status": "ACTIVE"}]):
        r = await client.get("/api/v1/marketing/diagnostics?days=7", headers=headers)
    assert r.status_code == 200
    assert r.json()[0]["code"] == "no_results" and r.json()[0]["campaign_name"] == "Camp A"


@pytest.mark.asyncio
async def test_funnel_crosses_ads_leads_and_sales(client, db_session, make_user):
    account, _, headers = await _ads_setup(db_session)
    now = datetime.now(timezone.utc) - timedelta(days=2)
    old = datetime.now(timezone.utc) - timedelta(days=60)

    def lead(ad, when):
        l = Lead(id=str(uuid.uuid4()), account_id=account.id, instagram_handle=str(uuid.uuid4())[:10], name="x",
                 source="manual", status="new", origin_ad_id=ad, captured_at=when)
        db_session.add(l)
        return l

    l1, l2, _l3, l_old = lead("AD1", now), lead("AD1", now), lead("AD2", now), lead("AD1", old)
    await db_session.flush()
    for l, amount in ((l1, 500.0), (l1, 300.0), (l_old, 999.0)):
        cust = Customer(account_id=account.id, name="c", lead_id=l.id)
        db_session.add(cust)
        await db_session.flush()
        db_session.add(Sale(account_id=account.id, customer_id=cust.id, amount=amount))
    # Venda de outra conta com o mesmo anúncio não entra
    other_tid, _ = await make_user()
    other = Lead(id=str(uuid.uuid4()), account_id=other_tid, instagram_handle="zz", name="z", source="manual",
                 status="new", origin_ad_id="AD1", captured_at=now)
    db_session.add(other)
    await db_session.flush()
    oc = Customer(account_id=other_tid, name="o", lead_id=other.id)
    db_session.add(oc)
    await db_session.flush()
    db_session.add(Sale(account_id=other_tid, customer_id=oc.id, amount=10000.0))
    await db_session.flush()

    ad_rows = [{"ad_id": "AD1", "ad_name": "Vídeo", "campaign_name": "C", "spend": "200", "actions": []},
               {"ad_id": "AD3", "ad_name": "Sem lead", "campaign_name": "C", "spend": "50", "actions": []}]
    with patch("app.services.ads_service.get_insights", new_callable=AsyncMock, return_value=ad_rows), \
         patch("app.services.ads_service.get_ad_names", new_callable=AsyncMock, return_value={"AD2": "Imagem"}):
        r = await client.get("/api/v1/marketing/funnel?days=30", headers=headers)
    assert r.status_code == 200
    data = r.json()
    rows = {row["ad_id"]: row for row in data["rows"]}
    assert rows["AD1"]["leads"] == 2 and rows["AD1"]["sales"] == 2 and rows["AD1"]["buyers"] == 1
    assert rows["AD1"]["revenue"] == 800.0 and rows["AD1"]["roas"] == 4.0 and rows["AD1"]["cost_per_lead"] == 100.0
    assert rows["AD2"]["ad_name"] == "Imagem" and rows["AD2"]["spend"] == 0 and rows["AD2"]["leads"] == 1
    assert rows["AD3"]["leads"] == 0 and rows["AD3"]["spend"] == 50
    assert data["rows"][0]["ad_id"] == "AD1"
    assert data["totals"]["revenue"] == 800.0 and data["totals"]["spend"] == 250.0 and data["totals"]["leads"] == 3
