import logging
from urllib.parse import urlencode

from fastapi import APIRouter, HTTPException, Depends, Query
from fastapi.responses import RedirectResponse
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select
import httpx

from app.core.database import get_db
from app.core.config import settings
from app.core.security import get_current_user
from app.models.user import User
from app.models.account import Account
from app.models.meta_connection import (
    MetaConnection,
    PROVIDER_INSTAGRAM, PROVIDER_WHATSAPP, PROVIDER_ADS, PROVIDERS,
    STATUS_ACTIVE, STATUS_REVOKED,
)
from app.schemas.auth import MetaAuthUrlResponse, MetaCallbackResponse
from app.schemas import OnboardingStatusResponse, SelectPlanRequest
from app.services.meta_token_service import (
    encrypt_token, decrypt_token, safe_decrypt_token, safe_encrypt_token,
    exchange_for_long_lived_token,
    create_signed_state, verify_signed_state,
)

logger = logging.getLogger(__name__)
router = APIRouter(prefix="/auth", tags=["auth"])

# ---------------------------------------------------------------------------
# Scope definitions
#
# Instagram: uses Facebook Login for Business (facebook.com/dialog/oauth).
#   "instagram_business_*" scopes belong to Instagram Login (instagram.com/oauth/authorize)
#   and are INCOMPATIBLE with the Facebook dialog — they return "Invalid Scope".
#   The correct scopes for multi-tenant SaaS via Business Portfolio are the classic ones below.
#
# WhatsApp: the simple OAuth redirect is a placeholder for development/test only.
#   Production multi-tenant (onboarding third-party WABAs) requires:
#     1. Inscription in the Meta Tech Provider Program
#     2. Embedded Signup flow via the Facebook JS SDK (FB.login with a config_id)
#     3. Receiving WABA data via postMessage, not a redirect callback
#   TODO: replace PROVIDER_WHATSAPP flow with Embedded Signup after Tech Provider approval.
# ---------------------------------------------------------------------------

_PROVIDER_SCOPES: dict[str, str] = {
    PROVIDER_INSTAGRAM: (
        "pages_show_list,"
        "pages_read_engagement,"
        "instagram_manage_comments"
    ),
    PROVIDER_WHATSAPP: (
        "whatsapp_business_messaging,"
        "whatsapp_business_management,"
        "pages_show_list"
    ),
    PROVIDER_ADS: (
        "ads_management,"
        "ads_read,"
        "business_management,"
        "pages_show_list"
    ),
}

# Legacy scopes used by the original onboarding flow
_LEGACY_SCOPES = (
    "instagram_basic,instagram_content_publish,"
    "pages_read_engagement,pages_manage_metadata,"
    "ads_management,ads_read"
)


# ---------------------------------------------------------------------------
# Legacy endpoint (keeps onboarding flow working)
# ---------------------------------------------------------------------------

@router.get("/meta/login", response_model=MetaAuthUrlResponse)
async def meta_login():
    """Legacy: generate a Meta OAuth URL with combined scopes for onboarding."""
    params = {
        "client_id": settings.meta_app_id,
        "redirect_uri": settings.meta_redirect_uri,
        "scope": _LEGACY_SCOPES,
        "response_type": "code",
    }
    auth_url = f"{settings.meta_dialog_url}?{urlencode(params)}"
    return MetaAuthUrlResponse(auth_url=auth_url)


# ---------------------------------------------------------------------------
# New multi-provider start endpoint
# ---------------------------------------------------------------------------

@router.get("/meta/start", response_model=MetaAuthUrlResponse)
async def meta_start(
    account_id: str = Query(..., description="Tenant account_id"),
    provider: str = Query(..., description="instagram | whatsapp | ads"),
):
    """Generate a provider-specific OAuth URL with a signed anti-CSRF state."""
    if provider not in PROVIDERS:
        raise HTTPException(status_code=400, detail=f"Provider must be one of: {', '.join(PROVIDERS)}")

    state = create_signed_state(account_id, provider)
    params = {
        "client_id": settings.meta_app_id,
        "redirect_uri": settings.meta_redirect_uri,
        "scope": _PROVIDER_SCOPES[provider],
        "response_type": "code",
        "state": state,
    }
    auth_url = f"{settings.meta_dialog_url}?{urlencode(params)}"
    return MetaAuthUrlResponse(auth_url=auth_url)


# ---------------------------------------------------------------------------
# Unified callback (handles both legacy and new multi-provider flows)
# ---------------------------------------------------------------------------

@router.get("/meta/callback", response_model=MetaCallbackResponse)
async def meta_callback(
    code: str = Query(None),
    state: str = Query(None),
    error: str = Query(None),
    error_description: str = Query(None),
    db: AsyncSession = Depends(get_db),
):
    # --- User denied permission ---
    if error:
        raise HTTPException(
            status_code=400,
            detail=f"OAuth denied: {error_description or error}",
        )

    if not code:
        raise HTTPException(status_code=400, detail="Missing authorization code.")

    # --- Exchange code for short-lived token ---
    async with httpx.AsyncClient() as client:
        token_resp = await client.get(
            f"{settings.meta_graph_url}/oauth/access_token",
            params={
                "client_id": settings.meta_app_id,
                "client_secret": settings.meta_oauth_client_secret or settings.meta_app_secret,
                "redirect_uri": settings.meta_redirect_uri,
                "code": code,
            },
        )
    token_data = token_resp.json()
    if "access_token" not in token_data:
        logger.error("Token exchange failed: %s", token_data)
        raise HTTPException(status_code=400, detail="Meta authentication failed.")

    short_lived_token = token_data["access_token"]

    # --- Exchange for long-lived token (~60 days) ---
    try:
        ll = await exchange_for_long_lived_token(short_lived_token)
        access_token = ll["access_token"]
        expires_at = ll["expires_at"]
    except ValueError:
        # Fall back to short-lived if exchange fails (e.g. test apps)
        access_token = short_lived_token
        expires_at = None

    # --- Fetch user info and pages ---
    async with httpx.AsyncClient() as client:
        me_resp = await client.get(
            f"{settings.meta_graph_url}/me",
            params={"fields": "id,name,accounts{id,name,access_token,instagram_business_account}", "access_token": access_token},
        )
    me_data = me_resp.json()
    logger.info("Meta /me response: %s", me_data)

    meta_user_id = me_data.get("id")
    fb_user_name = me_data.get("name", "Unknown")
    pages = me_data.get("accounts", {}).get("data", [])

    # Página do Facebook é opcional para o provider "ads" (a Marketing API usa o
    # token de usuário; a página só é necessária depois, ao criar criativos).
    # Para os demais fluxos ela continua obrigatória — o erro é levantado adiante.
    page = pages[0] if pages else None
    page_id = page["id"] if page else None
    page_name = page.get("name", "") if page else ""
    page_access_token = page.get("access_token", access_token) if page else access_token

    ig_biz_id: str | None = None
    if page and "instagram_business_account" in page:
        ig_biz_id = page["instagram_business_account"].get("id")

    # -----------------------------------------------------------------------
    # New multi-provider flow (state present)
    # -----------------------------------------------------------------------
    if state:
        try:
            state_payload = verify_signed_state(state)
        except ValueError as exc:
            raise HTTPException(status_code=400, detail=str(exc))

        tenant_account_id = state_payload["account_id"]
        provider = state_payload["provider"]

        # Verify tenant exists
        result = await db.execute(select(Account).where(Account.id == tenant_account_id))
        account = result.scalar_one_or_none()
        if not account:
            raise HTTPException(status_code=404, detail="Conta não encontrada.")

        # Upsert MetaConnection
        conn_result = await db.execute(
            select(MetaConnection).where(
                MetaConnection.account_id == tenant_account_id,
                MetaConnection.provider == provider,
            )
        )
        connection = conn_result.scalar_one_or_none()

        ad_account_id: str | None = None
        waba_id_val: str | None = None

        if provider == PROVIDER_ADS:
            ad_account_id = await _discover_ad_account(access_token, meta_user_id)
            if not ad_account_id:
                raise HTTPException(
                    status_code=400,
                    detail=(
                        "Nenhuma conta de anúncios encontrada para este usuário. "
                        "Crie uma no Gerenciador de Anúncios da Meta primeiro."
                    ),
                )
        elif provider == PROVIDER_WHATSAPP:
            waba_id_val = await _discover_waba(access_token, meta_user_id)

        if provider != PROVIDER_ADS and not page:
            raise HTTPException(
                status_code=400,
                detail="Nenhuma Página do Facebook encontrada. Crie uma Página primeiro.",
            )

        # Ads: a Marketing API é chamada com o token de USUÁRIO (o token da
        # página não carrega as permissões ads_management/ads_read).
        token_to_store = access_token if provider == PROVIDER_ADS else page_access_token
        encrypted_token = encrypt_token(token_to_store)
        scopes_str = _PROVIDER_SCOPES.get(provider, "")

        if connection:
            connection.access_token_encrypted = encrypted_token
            connection.expires_at = expires_at
            connection.meta_user_id = meta_user_id
            connection.page_id = page_id
            connection.ig_business_account_id = ig_biz_id
            connection.waba_id = waba_id_val
            connection.ad_account_id = ad_account_id
            connection.scopes = scopes_str
            connection.status = STATUS_ACTIVE
        else:
            connection = MetaConnection(
                account_id=tenant_account_id,
                provider=provider,
                meta_user_id=meta_user_id,
                page_id=page_id,
                ig_business_account_id=ig_biz_id,
                waba_id=waba_id_val,
                ad_account_id=ad_account_id,
                access_token_encrypted=encrypted_token,
                token_type="long_lived",
                expires_at=expires_at,
                scopes=scopes_str,
                status=STATUS_ACTIVE,
            )
            db.add(connection)

        await db.flush()
        await db.refresh(account)

        # Popup: redireciona para a página de sucesso do front, que avisa a
        # janela principal via postMessage (OAUTH_SUCCESS) e se fecha sozinha.
        return RedirectResponse(
            url=f"{settings.app_url}/oauth/success?provider={provider}&username={page_name or ''}",
            status_code=302,
        )

    # -----------------------------------------------------------------------
    # Legacy onboarding flow (no state)
    # -----------------------------------------------------------------------
    result = await db.execute(select(Account).where(Account.meta_page_id == page_id))
    existing = result.scalar_one_or_none()

    if existing:
        existing.meta_access_token = safe_encrypt_token(page_access_token)
        existing.meta_page_name = page_name
        existing.brand_name = fb_user_name
        existing.onboarding_step = 2
        account = existing
    else:
        account = Account(
            brand_name=fb_user_name,
            meta_page_id=page_id,
            meta_page_name=page_name,
            meta_access_token=safe_encrypt_token(page_access_token),
            onboarding_step=2,
        )
        db.add(account)

    await db.flush()
    await db.refresh(account)

    return MetaCallbackResponse(
        success=True,
        account_id=account.id,
        brand_name=account.brand_name,
        page_name=account.meta_page_name,
        onboarding_step=account.onboarding_step,
    )


# ---------------------------------------------------------------------------
# List connections for a tenant
# ---------------------------------------------------------------------------

@router.get("/meta/connections")
async def list_connections(
    account_id: str | None = Query(None),
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    tid = account_id or current_user.tenant_id
    result = await db.execute(
        select(MetaConnection).where(MetaConnection.account_id == tid)
    )
    connections = result.scalars().all()
    return [_serialize_connection(c) for c in connections]


# ---------------------------------------------------------------------------
# Disconnect / revoke a connection
# ---------------------------------------------------------------------------

@router.delete("/meta/connections/{connection_id}")
async def delete_connection(
    connection_id: str,
    account_id: str = Query(...),
    db: AsyncSession = Depends(get_db),
):
    result = await db.execute(
        select(MetaConnection).where(
            MetaConnection.id == connection_id,
            MetaConnection.account_id == account_id,
        )
    )
    connection = result.scalar_one_or_none()
    if not connection:
        raise HTTPException(status_code=404, detail="Conexão não encontrada.")

    # Attempt to revoke token at Meta (best-effort)
    try:
        token = decrypt_token(connection.access_token_encrypted)
        async with httpx.AsyncClient() as client:
            await client.delete(
                f"{settings.meta_graph_url}/{connection.meta_user_id}/permissions",
                params={"access_token": token},
            )
    except Exception as exc:
        logger.warning("Could not revoke Meta token: %s", exc)

    await db.delete(connection)
    return {"success": True, "detail": "Conexão removida."}


# ---------------------------------------------------------------------------
# Existing onboarding helpers (unchanged)
# ---------------------------------------------------------------------------

@router.get("/onboarding/status", response_model=OnboardingStatusResponse)
async def onboarding_status(
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    result = await db.execute(select(Account).where(Account.id == current_user.tenant_id))
    account = result.scalar_one_or_none()
    if not account:
        raise HTTPException(status_code=404, detail="Conta não encontrada")

    return OnboardingStatusResponse(
        account_id=account.id,
        brand_name=account.brand_name,
        page_name=account.meta_page_name,
        plan_type=account.plan_type,
        onboarding_step=account.onboarding_step,
        instagram_connected=account.onboarding_step >= 2,
        ad_account_selected=account.onboarding_step >= 3,
    )


@router.post("/onboarding/plan")
async def select_plan(
    data: SelectPlanRequest,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    if data.plan_type not in ("autonomo", "agencia"):
        raise HTTPException(status_code=400, detail="Plano inválido. Escolha 'autonomo' ou 'agencia'.")

    result = await db.execute(select(Account).where(Account.id == current_user.tenant_id))
    account = result.scalar_one_or_none()
    if not account:
        raise HTTPException(status_code=404, detail="Conta não encontrada")

    account.plan_type = data.plan_type
    if account.onboarding_step < 1:
        account.onboarding_step = 1

    await db.flush()
    await db.refresh(account)

    return {"success": True, "plan_type": account.plan_type, "onboarding_step": account.onboarding_step}


@router.post("/onboarding/complete-step")
async def complete_step(
    step: int = Query(...),
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    result = await db.execute(select(Account).where(Account.id == current_user.tenant_id))
    account = result.scalar_one_or_none()
    if not account:
        raise HTTPException(status_code=404, detail="Conta não encontrada")

    if step > account.onboarding_step:
        account.onboarding_step = step
        await db.flush()
        await db.refresh(account)

    return {"success": True, "onboarding_step": account.onboarding_step}


@router.get("/meta/ad-accounts")
async def list_ad_accounts(
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    result = await db.execute(select(Account).where(Account.id == current_user.tenant_id))
    account = result.scalar_one_or_none()
    if not account:
        raise HTTPException(status_code=404, detail="Conta não encontrada")

    token = safe_decrypt_token(account.meta_access_token)
    async with httpx.AsyncClient() as client:
        resp = await client.get(
            f"{settings.meta_graph_url}/{account.meta_page_id}/adaccounts",
            params={
                "access_token": token,
                "fields": "id,name,account_status,currency,amount_spent",
            },
        )
    data = resp.json()
    ad_accounts = data.get("data", [])
    return {
        "ad_accounts": [
            {
                "id": a["id"],
                "name": a.get("name", ""),
                "account_status": a.get("account_status", 0),
                "currency": a.get("currency", "BRL"),
            }
            for a in ad_accounts
        ]
    }


# ---------------------------------------------------------------------------
# Private helpers
# ---------------------------------------------------------------------------

def _serialize_connection(c: MetaConnection) -> dict:
    return {
        "id": c.id,
        "provider": c.provider,
        "page_id": c.page_id,
        "ig_business_account_id": c.ig_business_account_id,
        "waba_id": c.waba_id,
        "phone_number": c.phone_number,
        "ad_account_id": c.ad_account_id,
        "status": c.status,
        "expires_at": c.expires_at.isoformat() if c.expires_at else None,
        "scopes": c.scopes.split(",") if c.scopes else [],
        "created_at": c.created_at.isoformat(),
    }


async def _discover_ad_account(token: str, meta_user_id: str) -> str | None:
    try:
        async with httpx.AsyncClient() as client:
            resp = await client.get(
                f"{settings.meta_graph_url}/me/adaccounts",
                params={"access_token": token, "fields": "id", "limit": "1"},
            )
        data = resp.json().get("data", [])
        return data[0]["id"] if data else None
    except Exception as exc:
        logger.warning("Could not discover ad account: %s", exc)
        return None


async def _discover_waba(token: str, meta_user_id: str) -> str | None:
    try:
        async with httpx.AsyncClient() as client:
            resp = await client.get(
                f"{settings.meta_graph_url}/{meta_user_id}/whatsapp_business_accounts",
                params={"access_token": token, "fields": "id", "limit": "1"},
            )
        data = resp.json().get("data", [])
        return data[0]["id"] if data else None
    except Exception as exc:
        logger.warning("Could not discover WABA: %s", exc)
        return None
