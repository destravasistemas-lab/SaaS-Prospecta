"""
Assistente de campanha: cria campanha, conjunto, criativo e anúncio numa
chamada; apaga a campanha se um passo falhar.
"""
from unittest.mock import AsyncMock, patch

import pytest

from tests.test_marketing_flow import _ads_setup

BASE = {
    "name": "Clareamento",
    "goal": "whatsapp",
    "daily_budget_cents": 3000,
    "targeting": {"age_min": 25, "age_max": 45, "genders": [2],
                  "locations": [{"key": "2510", "type": "city"}, {"key": "449", "type": "region"}]},
    "creative": {"name": "x", "message": "Sorriso novo em 1 sessão", "image_url": "https://cdn/x.jpg"},
    "headline": "Fale no WhatsApp",
    "welcome_message": "Olá! Vi o anúncio do clareamento.",
}


def _mocks(creative=None, ad=None):
    return (
        patch("app.services.ads_service.create_campaign", new_callable=AsyncMock, return_value={"id": "C9"}),
        patch("app.services.ads_service.create_ad_set", new_callable=AsyncMock, return_value={"id": "S9"}),
        patch("app.services.ads_service.create_ad_creative", new_callable=AsyncMock, return_value=creative or {"id": "CR9"}),
        patch("app.services.ads_service.create_ad", new_callable=AsyncMock, return_value=ad or {"id": "A9"}),
        patch("app.services.ads_service.delete_campaign", new_callable=AsyncMock, return_value={"success": True}),
    )


@pytest.mark.asyncio
async def test_whatsapp_campaign_end_to_end(client, db_session):
    _, conn, headers = await _ads_setup(db_session)
    m_camp, m_set, m_cr, m_ad, m_del = _mocks()
    with m_camp as camp, m_set as adset, m_cr as cr, m_ad as ad, m_del as delete:
        r = await client.post("/api/v1/marketing/quick-campaign", json={**BASE, "publish": True}, headers=headers)
    assert r.status_code == 201, r.text
    assert r.json() == {"campaign_id": "C9", "ad_set_id": "S9", "ad_id": "A9", "status": "ACTIVE"}

    assert camp.call_args.args[3] == "OUTCOME_ENGAGEMENT" and camp.call_args.args[4] == "ACTIVE"
    kw = adset.call_args.kwargs
    assert kw["optimization_goal"] == "CONVERSATIONS" and kw["destination_type"] == "WHATSAPP"
    assert kw["promoted_object"] == {"page_id": conn.page_id} and kw["status"] == "ACTIVE"
    assert kw["targeting"]["geo_locations"] == {"regions": [{"key": "449"}], "cities": [{"key": "2510"}]}
    assert kw["targeting"]["genders"] == [2]
    assert cr.call_args.kwargs["whatsapp"] is True
    assert cr.call_args.kwargs["welcome_message"] == "Olá! Vi o anúncio do clareamento."
    assert ad.call_args.kwargs["status"] == "ACTIVE"
    delete.assert_not_called()


@pytest.mark.asyncio
async def test_failed_creative_removes_the_campaign(client, db_session):
    _, _, headers = await _ads_setup(db_session)
    m_camp, m_set, m_cr, m_ad, m_del = _mocks(creative={"error": {"error_user_msg": "Imagem muito pequena."}})
    with m_camp, m_set, m_cr, m_ad as ad, m_del as delete:
        r = await client.post("/api/v1/marketing/quick-campaign", json=BASE, headers=headers)
    assert r.status_code == 400
    assert r.json()["detail"] == {"step": "creative", "message": "Imagem muito pequena."}
    delete.assert_awaited_once()
    assert delete.call_args.args[1] == "C9"
    ad.assert_not_called()


@pytest.mark.asyncio
async def test_traffic_needs_link_and_whatsapp_refuses_posts(client, db_session):
    _, _, headers = await _ads_setup(db_session)
    m_camp, m_set, m_cr, m_ad, m_del = _mocks()
    with m_camp as camp, m_set, m_cr, m_ad, m_del:
        r = await client.post("/api/v1/marketing/quick-campaign", json={**BASE, "goal": "traffic"}, headers=headers)
        assert r.status_code == 422 and r.json()["detail"]["step"] == "creative"
        r = await client.post("/api/v1/marketing/quick-campaign", json={
            **BASE, "creative": {"name": "x", "source_instagram_media_id": "IG1", "link_url": "https://a.b"},
        }, headers=headers)
        assert r.status_code == 422
        r = await client.post("/api/v1/marketing/quick-campaign", json={**BASE, "end_date": "2020-01-01"}, headers=headers)
        assert r.status_code == 422 and r.json()["detail"]["step"] == "budget"
        camp.assert_not_called()


@pytest.mark.asyncio
async def test_traffic_campaign_paused_by_default(client, db_session):
    _, _, headers = await _ads_setup(db_session)
    body = {**BASE, "goal": "traffic", "creative": {**BASE["creative"], "link_url": "https://clinica.com"},
            "end_date": "2099-01-31"}
    m_camp, m_set, m_cr, m_ad, m_del = _mocks()
    with m_camp as camp, m_set as adset, m_cr as cr, m_ad, m_del:
        r = await client.post("/api/v1/marketing/quick-campaign", json=body, headers=headers)
    assert r.status_code == 201 and r.json()["status"] == "PAUSED"
    assert camp.call_args.args[3] == "OUTCOME_TRAFFIC"
    assert adset.call_args.kwargs["destination_type"] is None and adset.call_args.kwargs["promoted_object"] is None
    assert adset.call_args.kwargs["end_time"] == "2099-01-31T23:59:59-0300"
    assert cr.call_args.kwargs["whatsapp"] is False and cr.call_args.kwargs["welcome_message"] is None


@pytest.mark.asyncio
async def test_whatsapp_creative_and_ad_set_payloads_follow_meta_docs():
    from app.services import ads_service
    with patch("app.services.ads_service._request", new_callable=AsyncMock, return_value={"id": "1"}) as req:
        await ads_service.create_ad_creative("t", "act_1", "n", "PAGE", "msg", image_url="https://x/y.jpg",
                                             whatsapp=True, headline="Fale conosco", welcome_message="Oi!")
        link = req.call_args.kwargs["json"]["object_story_spec"]["link_data"]
        assert link["call_to_action"] == {"type": "WHATSAPP_MESSAGE", "value": {"app_destination": "WHATSAPP"}}
        assert link["link"] == "https://api.whatsapp.com/send" and link["name"] == "Fale conosco"
        assert link["page_welcome_message"]["text_format"]["message"]["autofill_message"]["content"] == "Oi!"

        await ads_service.create_ad_creative("t", "act_1", "n", "PAGE", "msg", video_id="V1", whatsapp=True)
        video = req.call_args.kwargs["json"]["object_story_spec"]["video_data"]
        assert video["video_id"] == "V1" and video["call_to_action"]["type"] == "WHATSAPP_MESSAGE"

        await ads_service.create_ad_set("t", "act_1", "C1", "S", 3000, optimization_goal="CONVERSATIONS",
                                        destination_type="WHATSAPP", promoted_object={"page_id": "PAGE"}, status="ACTIVE")
        payload = req.call_args.kwargs["json"]
        assert payload["destination_type"] == "WHATSAPP" and payload["promoted_object"] == {"page_id": "PAGE"}
        assert payload["status"] == "ACTIVE" and payload["billing_event"] == "IMPRESSIONS"
