"""
Utilities for Meta access-token lifecycle:
  - Fernet encryption/decryption of tokens at rest
  - Short-lived → long-lived token exchange (~60 days)
  - Long-lived token refresh
  - Signed OAuth state (anti-CSRF)
"""
import base64
import hashlib
import hmac
import json
import logging
import time
from datetime import datetime, timezone, timedelta

import httpx
from cryptography.fernet import Fernet, InvalidToken

from app.core.config import settings

logger = logging.getLogger(__name__)

_fernet: Fernet | None = None


def _get_fernet() -> Fernet:
    global _fernet
    if _fernet is None:
        if not settings.fernet_key:
            raise RuntimeError(
                "FERNET_KEY is not configured. "
                "Generate one with: python -c \"from cryptography.fernet import Fernet; print(Fernet.generate_key().decode())\""
            )
        _fernet = Fernet(settings.fernet_key.encode())
    return _fernet


def encrypt_token(token: str) -> str:
    return _get_fernet().encrypt(token.encode()).decode()


def decrypt_token(encrypted: str) -> str:
    try:
        return _get_fernet().decrypt(encrypted.encode()).decode()
    except InvalidToken as exc:
        raise ValueError("Token decryption failed — key mismatch or corrupted data") from exc


def safe_decrypt_token(token: str) -> str:
    """
    Decrypt a token, falling back to returning it as-is for legacy plaintext data
    already in the database before Fernet was introduced.
    Only use at read-time for the legacy Account.meta_access_token field.
    """
    if not token:
        return token
    try:
        return decrypt_token(token)
    except (ValueError, RuntimeError):
        return token


def safe_encrypt_token(token: str) -> str:
    """
    Encrypt a token, falling back to plaintext if FERNET_KEY is not configured.
    Only for the legacy Account.meta_access_token field — MetaConnection always
    requires full encryption via encrypt_token().
    """
    try:
        return encrypt_token(token)
    except RuntimeError:
        logger.warning("FERNET_KEY not set — storing legacy token as plaintext")
        return token


# ---------------------------------------------------------------------------
# Long-lived token exchange
# ---------------------------------------------------------------------------

async def exchange_for_long_lived_token(short_lived_token: str) -> dict:
    """Exchange a short-lived (~1 h) token for a long-lived one (~60 days)."""
    async with httpx.AsyncClient() as client:
        resp = await client.get(
            f"{settings.meta_graph_url}/oauth/access_token",
            params={
                "grant_type": "fb_exchange_token",
                "client_id": settings.meta_app_id,
                "client_secret": settings.meta_app_secret,
                "fb_exchange_token": short_lived_token,
            },
        )
    data = resp.json()
    if "access_token" not in data:
        raise ValueError(f"Token exchange failed: {data.get('error', data)}")

    expires_in = data.get("expires_in", 5_184_000)  # default ~60 days
    return {
        "access_token": data["access_token"],
        "token_type": "long_lived",
        "expires_at": datetime.now(timezone.utc) + timedelta(seconds=int(expires_in)),
    }


async def refresh_long_lived_token(token: str) -> dict:
    """Refresh a long-lived token to extend it by another ~60 days."""
    return await exchange_for_long_lived_token(token)


async def exchange_code_for_token(code: str) -> dict:
    """
    Exchange the `code` returned by the WhatsApp Embedded Signup JS SDK flow
    (FB.login with config_id, response_type=code) for an access token.

    Unlike the redirect-based OAuth flow, this exchange does NOT take a
    redirect_uri — the code comes from the JS SDK login dialog, not a
    server-side redirect.
    """
    async with httpx.AsyncClient() as client:
        resp = await client.get(
            f"{settings.meta_graph_url}/oauth/access_token",
            params={
                "client_id": settings.meta_app_id,
                "client_secret": settings.meta_app_secret,
                "code": code,
            },
        )
    data = resp.json()
    if "access_token" not in data:
        raise ValueError(f"Embedded Signup code exchange failed: {data.get('error', data)}")

    expires_in = data.get("expires_in")
    return {
        "access_token": data["access_token"],
        "expires_at": (
            datetime.now(timezone.utc) + timedelta(seconds=int(expires_in))
            if expires_in else None
        ),
    }


# ---------------------------------------------------------------------------
# Signed OAuth state (anti-CSRF)
# ---------------------------------------------------------------------------

def create_signed_state(account_id: str, provider: str) -> str:
    """Create a signed state string for the OAuth redirect."""
    payload = json.dumps({"account_id": account_id, "provider": provider, "ts": int(time.time())})
    encoded = base64.urlsafe_b64encode(payload.encode()).decode()
    sig = hmac.new(settings.secret_key.encode(), encoded.encode(), hashlib.sha256).hexdigest()
    return f"{encoded}.{sig}"


def verify_signed_state(state: str) -> dict:
    """Verify and decode a signed state string. Raises ValueError on failure."""
    try:
        encoded, sig = state.rsplit(".", 1)
    except ValueError as exc:
        raise ValueError("Malformed state parameter") from exc

    expected = hmac.new(settings.secret_key.encode(), encoded.encode(), hashlib.sha256).hexdigest()
    if not hmac.compare_digest(sig, expected):
        raise ValueError("Invalid state signature")

    try:
        payload = json.loads(base64.urlsafe_b64decode(encoded + "==").decode())
    except Exception as exc:
        raise ValueError("Could not decode state payload") from exc

    if int(time.time()) - payload.get("ts", 0) > 600:
        raise ValueError("State parameter expired (> 10 minutes)")

    return payload
