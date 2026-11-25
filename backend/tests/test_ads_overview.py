"""
Tela de Anúncios: status real de entrega, motivos de reprovação, situação da
conta e comparação com o período anterior.
"""
from datetime import date
from unittest.mock import AsyncMock, patch

import pytest

from app.routes.marketing import _period

from tests.test_marketing_flow import _ads_setup


def test_period_uses_full_days_and_previous_window():
    p = _period(7, today=date(2026, 11, 25))
    assert (p.since, p.until) == ("2026-11-18", "2026-11-24")
    assert (p.previous_since, p.previous_until) == ("2026-11-11", "2026-11-17")


@pytest.mark.asyncio
async def test_invalid_period_is_rejected(client, db_session):
    _, _, headers = await _ads_setup(db_session)
    assert (await client.get("/api/v1/marketing/overview?days=5", headers=headers)).status_code == 422


def _row(spend, leads, **extra):
    return {"spend": str(spend), "impressions": "1000", "reach": "800", "frequency": "1.25", "clicks": "20",
            "ctr": "2.0", "cpm": "10", "actions": [{"action_type": "lead", "value": str(leads)}], **extra}


@pytest.mark.asyncio
async def test_overview_compares_periods_and_lists_problem_ads(client, db_session):
    _, _, headers = await _ads_setup(db_session)

    async def fake_insights(token, node, since=None, until=None, level=None, **kw):
        current = since >= "2026" and until >= since and since == _period(7).since
        if level == "campaign":
            return [_row(100 if current else 50, 10 if current else 2, campaign_id="C1", campaign_name="Camp 1")]
        return [_row(100 if current else 50, 10 if current else 2)]

    problem = {"id": "AD9", "name": "Promo", "campaign_id": "C1", "adset_id": "S1", "effective_status": "DISAPPROVED",
               "ad_review_feedback": {"global": {"ADULT_CONTENT": "O anúncio contém conteúdo adulto."}},
               "issues_info": [{"error_summary": "Anúncio reprovado"}]}
    with patch("app.services.ads_service.get_insights", side_effect=fake_insights), \
         patch("app.services.ads_service.get_ad_account", new_callable=AsyncMock,
               return_value={"account_status": 3, "disable_reason": 0, "currency": "BRL"}), \
         patch("app.services.ads_service.list_problem_ads", new_callable=AsyncMock, return_value=[problem]):
        r = await client.get("/api/v1/marketing/overview?days=7", headers=headers)

    assert r.status_code == 200
    data = r.json()
    assert data["account"]["account_status"] == 3
    assert data["totals"]["current"]["spend"] == 100 and data["totals"]["previous"]["spend"] == 50
    assert data["totals"]["current"]["cost_per_result"] == 10.0
    assert data["campaigns"]["C1"]["current"]["results"] == 10
    assert data["campaigns"]["C1"]["previous"]["results"] == 2
    assert data["problems"][0]["effective_status"] == "DISAPPROVED"
    assert data["problems"][0]["reasons"] == ["O anúncio contém conteúdo adulto.", "Anúncio reprovado"]


@pytest.mark.asyncio
async def test_overview_survives_a_failing_meta_call(client, db_session):
    _, _, headers = await _ads_setup(db_session)
    with patch("app.services.ads_service.get_insights", new_callable=AsyncMock, return_value=[_row(10, 1)]), \
         patch("app.services.ads_service.get_ad_account", new_callable=AsyncMock, side_effect=RuntimeError("boom")), \
         patch("app.services.ads_service.list_problem_ads", new_callable=AsyncMock, return_value=[]):
        r = await client.get("/api/v1/marketing/overview?days=30", headers=headers)
    assert r.status_code == 200
    assert r.json()["account"]["account_status"] is None
    assert r.json()["totals"]["current"]["spend"] == 10


@pytest.mark.asyncio
async def test_lists_carry_real_delivery_status(client, db_session):
    _, _, headers = await _ads_setup(db_session)
    with patch("app.services.ads_service.list_campaigns", new_callable=AsyncMock, return_value=[
        {"id": "C1", "name": "Camp", "status": "ACTIVE", "effective_status": "WITH_ISSUES", "objective": "OUTCOME_LEADS",
         "issues_info": [{"error_summary": "Sem forma de pagamento"}]},
    ]):
        camp = (await client.get("/api/v1/marketing/campaigns", headers=headers)).json()[0]
    assert camp["status"] == "ACTIVE" and camp["effective_status"] == "WITH_ISSUES"
    assert camp["issues"] == ["Sem forma de pagamento"]

    with patch("app.services.ads_service.list_ads", new_callable=AsyncMock, return_value=[
        {"id": "AD1", "name": "Ad", "status": "ACTIVE", "effective_status": "DISAPPROVED",
         "ad_review_feedback": {"placement_specific": {"instagram": {"TEXT": "Texto em excesso."}}}},
    ]):
        ad = (await client.get("/api/v1/marketing/ad-sets/S1/ads", headers=headers)).json()[0]
    assert ad["effective_status"] == "DISAPPROVED" and ad["review_feedback"] == ["Texto em excesso."]


@pytest.mark.asyncio
async def test_campaign_summary_and_daily_results(client, db_session):
    _, _, headers = await _ads_setup(db_session)
    with patch("app.services.ads_service.get_insights", new_callable=AsyncMock, return_value=[_row(30, 3)]):
        s = (await client.get("/api/v1/marketing/campaigns/C1/summary?days=14", headers=headers)).json()
    assert s["current"]["results"] == 3 and s["previous"]["spend"] == 30

    with patch("app.services.ads_service.get_insights", new_callable=AsyncMock,
               return_value=[{**_row(5, 2), "date_start": "2026-11-20"}]) as mock:
        pts = (await client.get("/api/v1/marketing/campaigns/C1/insights?since=2026-11-01&until=2026-11-24",
                                headers=headers)).json()
    assert pts == [{"date": "2026-11-20", "spend": 5.0, "impressions": 1000, "clicks": 20, "results": 2.0}]
    assert "actions" in mock.call_args.kwargs["fields"]
