"""
Privacy & data deletion routes — required for Meta App Review.

Endpoints to register in the Meta App Dashboard:
  Privacy Policy URL      → https://your-domain/privacy
  Data Deletion URL       → https://your-domain/api/v1/privacy/data-deletion
  (Data Deletion Status)  → https://your-domain/api/v1/privacy/data-deletion-status?id=<code>

Spec: https://developers.facebook.com/docs/development/create-an-app/app-dashboard/data-deletion-callback
"""
import base64
import hashlib
import hmac
import json
import logging
import uuid

from fastapi import APIRouter, Depends, Form, HTTPException, Query, Request
from fastapi.responses import JSONResponse
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.config import settings
from app.core.database import get_db
from app.models.meta_connection import MetaConnection, STATUS_REVOKED

logger = logging.getLogger(__name__)
router = APIRouter(prefix="/privacy", tags=["privacy"])


# ---------------------------------------------------------------------------
# Privacy policy (human-readable JSON — point the App Dashboard URL here or
# serve a static HTML page from the frontend at /privacy)
# ---------------------------------------------------------------------------

@router.get("/policy")
async def privacy_policy():
    return {
        "app": settings.app_name,
        "last_updated": "2026-06-19",
        "data_collected": [
            "Facebook/Instagram Page ID and Page name",
            "Meta access tokens (stored encrypted at rest)",
            "Instagram Business Account ID",
            "WhatsApp Business Account ID (when connected)",
            "Ad Account IDs (when connected)",
            "Leads captured via Instagram comments and DMs (name, Instagram handle, optional email/phone)",
        ],
        "data_use": (
            "Data is used exclusively to provide the adStudioAI service to the account holder. "
            "Tokens are used to call the Meta Graph API on behalf of the authenticated user. "
            "No data is sold or shared with third parties."
        ),
        "data_retention": (
            "Access tokens are retained until the user disconnects the integration or "
            "requests account deletion. Leads are retained until deleted by the account holder."
        ),
        "deletion": (
            "Users can delete all their data by using the disconnect button in the app "
            "or by submitting a deletion request via the contact below."
        ),
        "contact": "davimvf1234@gmail.com",
    }


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
# Meta sends a POST with a `signed_request` form field when a user revokes
# permissions from Facebook Settings > Apps and Websites.
# We must verify the signature and return a confirmation URL + code.
# ---------------------------------------------------------------------------

@router.post("/data-deletion")
async def data_deletion_callback(signed_request: str = Form(...)):
    """
    Receive and verify a Meta data deletion request.
    Responds with the status URL and a confirmation code.
    """
    try:
        payload = _parse_signed_request(signed_request)
    except ValueError as exc:
        logger.warning("Invalid data deletion signed_request: %s", exc)
        raise HTTPException(status_code=400, detail=str(exc))

    user_id = payload.get("user_id", "unknown")
    confirmation_code = str(uuid.uuid4()).replace("-", "")[:16].upper()

    logger.info(
        "Data deletion requested for Meta user_id=%s — confirmation_code=%s",
        user_id,
        confirmation_code,
    )

    # TODO: enqueue an async job to delete all MetaConnections and Leads
    # associated with this meta_user_id across all tenants.

    status_url = (
        f"{settings.meta_redirect_uri.split('/api/')[0]}"
        f"/api/v1/privacy/data-deletion-status?id={confirmation_code}"
    )

    return {"url": status_url, "confirmation_code": confirmation_code}


# ---------------------------------------------------------------------------
# Data deletion status (linked from the callback response)
# ---------------------------------------------------------------------------

@router.get("/data-deletion-status")
async def data_deletion_status(id: str = Query(...)):
    """
    Status page for a data deletion request.
    The URL returned in /data-deletion is this endpoint.
    """
    return {
        "confirmation_code": id,
        "status": "received",
        "message": (
            "Your data deletion request has been received and will be processed "
            "within 30 days. If you have questions, contact davimvf1234@gmail.com."
        ),
    }


# ---------------------------------------------------------------------------
# Private helpers
# ---------------------------------------------------------------------------

def _parse_signed_request(signed_request: str) -> dict:
    """
    Decode and verify a Meta signed_request.
    Format: base64url(HMAC_SHA256_signature).base64url(json_payload)
    """
    try:
        encoded_sig, encoded_payload = signed_request.split(".", 1)
    except ValueError as exc:
        raise ValueError("Malformed signed_request — missing dot separator") from exc

    def _b64_decode(s: str) -> bytes:
        s += "=" * (-len(s) % 4)
        return base64.urlsafe_b64decode(s)

    signature = _b64_decode(encoded_sig)
    expected = hmac.new(
        settings.meta_app_secret.encode(), encoded_payload.encode(), hashlib.sha256
    ).digest()

    if not hmac.compare_digest(signature, expected):
        raise ValueError("signed_request signature mismatch")

    payload = json.loads(_b64_decode(encoded_payload).decode())

    if payload.get("algorithm", "").upper() != "HMAC-SHA256":
        raise ValueError(f"Unsupported algorithm: {payload.get('algorithm')}")

    return payload
