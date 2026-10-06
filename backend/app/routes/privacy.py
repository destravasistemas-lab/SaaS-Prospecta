"""
Privacy & data deletion routes — required for Meta App Review.

Endpoints to register in the Meta App Dashboard:
  Privacy Policy URL      → https://your-domain/privacy
  Terms of Service URL    → https://your-domain/terms
  Data Deletion URL       → https://your-domain/api/v1/privacy/data-deletion
  Deauthorize URL         → https://your-domain/api/v1/privacy/deauthorize
  (Data Deletion Status)  → https://your-domain/data-deletion?code=<code>

Spec: https://developers.facebook.com/docs/development/create-an-app/app-dashboard/data-deletion-callback
"""
import base64
import hashlib
import hmac
import json
import logging
import secrets
from datetime import datetime, timezone

from fastapi import APIRouter, Depends, Form, HTTPException, Query
from sqlalchemy import select, delete, update, or_
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.config import settings
from app.core.database import get_db
from app.core.i18n import t
from app.models.automation import Customer
from app.models.conversation import Conversation
from app.models.lead import Lead
from app.models.message import Message
from app.models.meta_connection import MetaConnection, STATUS_REVOKED
from app.models.privacy import DataDeletionRequest

logger = logging.getLogger(__name__)
router = APIRouter(prefix="/privacy", tags=["privacy"])


# ---------------------------------------------------------------------------
# Privacy policy (machine-readable summary — the human-readable page is the
# frontend route /privacy)
# ---------------------------------------------------------------------------

@router.get("/policy")
async def privacy_policy():
    return {
        "app": settings.app_name,
        "last_updated": "2026-10-06",
        "policy_url": f"{settings.app_url}/privacy",
        "terms_url": f"{settings.app_url}/terms",
        "data_deletion_url": f"{settings.app_url}/data-deletion",
        "data_collected": [
            "Account data: name, email and password hash of platform users",
            "Meta access tokens (encrypted at rest with Fernet/AES)",
            "Facebook Page ID/name, Instagram professional account ID/username",
            "WhatsApp Business Account ID, phone number ID and display number",
            "Ad account IDs, campaigns, ad sets, ads and insights (when Meta Ads is connected)",
            "Messages exchanged with the business's customers on WhatsApp and Instagram Direct",
            "Contacts/leads: name, Instagram username, phone, email, WhatsApp opt-in status",
        ],
        "data_use": (
            "Data is used exclusively to provide the service to the business that connected "
            "its accounts: shared inbox, automations, publishing, analytics and ad management. "
            "Meta Platform Data is never sold, never used for unrelated advertising and never "
            "shared with third parties except the processors needed to run the service."
        ),
        "data_retention": (
            "Access tokens are kept until the integration is disconnected, the app is removed "
            "in Meta settings, or account deletion is requested. Messages and leads are kept "
            "until deleted by the account holder or within 30 days of a deletion request."
        ),
        "deletion": (
            "Remove the app in Facebook/Instagram Settings > Apps and Websites (automatic "
            "deletion via callback), use the Disconnect button in the app, or email us."
        ),
        "contact": settings.support_email,
    }


# ---------------------------------------------------------------------------
# Deauthorize callback — user removed the app in Meta settings
# ---------------------------------------------------------------------------

@router.post("/deauthorize")
async def deauthorize_callback(
    signed_request: str = Form(...),
    db: AsyncSession = Depends(get_db),
):
    try:
        payload = _parse_signed_request(signed_request)
    except ValueError as exc:
        logger.warning("Invalid deauthorize signed_request: %s", exc)
        raise HTTPException(status_code=400, detail=str(exc))

    user_id = str(payload.get("user_id") or "")
    revoked_count = 0

    if user_id:
        result = await db.execute(
            select(MetaConnection).where(MetaConnection.meta_user_id == user_id)
        )
        connections = result.scalars().all()
        for connection in connections:
            connection.status = STATUS_REVOKED
            # The token is no longer valid — don't keep it around
            connection.access_token_encrypted = ""
        revoked_count = len(connections)
        await db.flush()

    logger.info(
        "Meta deauthorization received for user_id=%s; revoked_connections=%s",
        user_id or "unknown",
        revoked_count,
    )

    return {"success": True}


# ---------------------------------------------------------------------------
# Meta Data Deletion Callback
#
# Meta sends a POST with a `signed_request` form field when a user removes the
# app and asks for their data to be deleted. We verify the signature, delete
# the data synchronously and return a status URL + confirmation code.
# ---------------------------------------------------------------------------

@router.post("/data-deletion")
async def data_deletion_callback(
    signed_request: str = Form(...),
    db: AsyncSession = Depends(get_db),
):
    """Receive a Meta data deletion request, delete the user's data and return the status URL."""
    try:
        payload = _parse_signed_request(signed_request)
    except ValueError as exc:
        logger.warning("Invalid data deletion signed_request: %s", exc)
        raise HTTPException(status_code=400, detail=str(exc))

    user_id = str(payload.get("user_id") or "")
    confirmation_code = secrets.token_hex(8).upper()

    req = DataDeletionRequest(
        confirmation_code=confirmation_code,
        meta_user_id=user_id or None,
        source="meta_callback",
    )
    db.add(req)
    await db.flush()

    summary = await purge_meta_user_data(db, user_id) if user_id else {}
    req.summary = summary
    req.status = "completed"
    req.completed_at = datetime.now(timezone.utc)
    await db.flush()

    logger.info(
        "Data deletion completed for Meta user_id=%s — code=%s summary=%s",
        user_id or "unknown", confirmation_code, summary,
    )

    status_url = f"{settings.app_url}/data-deletion?code={confirmation_code}"
    return {"url": status_url, "confirmation_code": confirmation_code}


@router.get("/data-deletion-status")
async def data_deletion_status(
    id: str = Query(..., description="Confirmation code returned by the deletion callback"),
    db: AsyncSession = Depends(get_db),
):
    """Public status of a data deletion request (linked from the status page)."""
    result = await db.execute(
        select(DataDeletionRequest).where(DataDeletionRequest.confirmation_code == id)
    )
    req = result.scalar_one_or_none()
    if not req:
        raise HTTPException(status_code=404, detail=t(
            "Código de confirmação não encontrado.", "Confirmation code not found."
        ))
    return {
        "confirmation_code": req.confirmation_code,
        "status": req.status,
        "requested_at": req.created_at.isoformat() if req.created_at else None,
        "completed_at": req.completed_at.isoformat() if req.completed_at else None,
        "message": (
            t("Seus dados foram excluídos.", "Your data has been deleted.")
            if req.status == "completed"
            else t(
                "Sua solicitação foi recebida e será processada em até 30 dias.",
                "Your request was received and will be processed within 30 days.",
            )
        ),
        "contact": settings.support_email,
    }


async def purge_meta_user_data(db: AsyncSession, meta_user_id: str) -> dict:
    """
    Deletes everything tied to a Meta user ID:
      - connections (tokens, page/IG/WABA identifiers) authorized by that user;
      - leads keyed by that ID (when the person is a customer of a tenant) and
        their conversations/messages.
    """
    conn_result = await db.execute(
        delete(MetaConnection).where(MetaConnection.meta_user_id == meta_user_id)
    )

    lead_ids = (await db.execute(
        select(Lead.id).where(or_(
            Lead.instagram_handle == meta_user_id,
            Lead.ig_user_id == meta_user_id,
        ))
    )).scalars().all()

    conv_ids: list[str] = []
    msg_count = 0
    if lead_ids:
        conv_ids = (await db.execute(
            select(Conversation.id).where(Conversation.customer_id.in_(lead_ids))
        )).scalars().all()
        if conv_ids:
            msg_result = await db.execute(delete(Message).where(Message.conversation_id.in_(conv_ids)))
            msg_count = msg_result.rowcount or 0
            await db.execute(delete(Conversation).where(Conversation.id.in_(conv_ids)))
        await db.execute(update(Customer).where(Customer.lead_id.in_(lead_ids)).values(lead_id=None))
        await db.execute(delete(Lead).where(Lead.id.in_(lead_ids)))

    await db.flush()
    return {
        "connections": conn_result.rowcount or 0,
        "leads": len(lead_ids),
        "conversations": len(conv_ids),
        "messages": msg_count,
    }


# ---------------------------------------------------------------------------
# Private helpers
# ---------------------------------------------------------------------------

def _parse_signed_request(signed_request: str) -> dict:
    """
    Decode and verify a Meta signed_request.
    Format: base64url(HMAC_SHA256_signature).base64url(json_payload)

    Facebook Login uses META_APP_SECRET; the Instagram Login app signs with
    IG_APP_SECRET — both are accepted.
    """
    try:
        encoded_sig, encoded_payload = signed_request.split(".", 1)
    except ValueError as exc:
        raise ValueError("Malformed signed_request — missing dot separator") from exc

    def _b64_decode(s: str) -> bytes:
        s += "=" * (-len(s) % 4)
        return base64.urlsafe_b64decode(s)

    signature = _b64_decode(encoded_sig)
    valid = False
    for secret in (settings.meta_app_secret, settings.ig_app_secret):
        if not secret:
            continue
        expected = hmac.new(secret.encode(), encoded_payload.encode(), hashlib.sha256).digest()
        if hmac.compare_digest(signature, expected):
            valid = True
            break
    if not valid:
        raise ValueError("signed_request signature mismatch")

    payload = json.loads(_b64_decode(encoded_payload).decode())

    if payload.get("algorithm", "").upper() != "HMAC-SHA256":
        raise ValueError(f"Unsupported algorithm: {payload.get('algorithm')}")

    return payload
