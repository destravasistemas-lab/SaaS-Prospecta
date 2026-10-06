import asyncio
import logging

from fastapi import FastAPI, Request
from fastapi.exception_handlers import http_exception_handler
from fastapi.openapi.utils import get_openapi
from starlette.exceptions import HTTPException as StarletteHTTPException
from fastapi.middleware.cors import CORSMiddleware
from contextlib import asynccontextmanager

from sqlalchemy import text

from app.core.config import settings
from app.core.database import engine, Base
from app.core.i18n import parse_lang, set_lang, reset_lang, translate_detail
from app.routes import auth, webhook, dashboard, leads, accounts, automations, privacy, instagram, instagram_api
from app.routes import auth_jwt, conversations, messages, ws, whatsapp, payments, tenants, clients
from app.routes import auth_email
from app.routes import admin as admin_routes
from app.routes import marketing
from app.routes import studio
from app.routes import ai as ai_routes

# Register all models with Base.metadata so create_all creates every table
import app.models.meta_connection   # noqa: F401
import app.models.user              # noqa: F401
import app.models.conversation      # noqa: F401
import app.models.message           # noqa: F401
import app.models.subscription      # noqa: F401
import app.models.schedule          # noqa: F401
import app.models.client_assignment # noqa: F401
import app.models.ai                # noqa: F401
import app.models.privacy           # noqa: F401

logging.basicConfig(level=logging.INFO)


_MIGRATIONS = [
    # Add WhatsApp-specific columns to meta_connections (safe — IF NOT EXISTS)
    "ALTER TABLE meta_connections ADD COLUMN IF NOT EXISTS phone_number_id VARCHAR(100)",
    "ALTER TABLE meta_connections ADD COLUMN IF NOT EXISTS phone_number VARCHAR(30)",
    "ALTER TABLE meta_connections ADD COLUMN IF NOT EXISTS meta_templates JSON",
    "ALTER TABLE meta_connections ADD COLUMN IF NOT EXISTS conv_count_marketing INTEGER NOT NULL DEFAULT 0",
    "ALTER TABLE meta_connections ADD COLUMN IF NOT EXISTS conv_count_utility INTEGER NOT NULL DEFAULT 0",
    "ALTER TABLE meta_connections ADD COLUMN IF NOT EXISTS conv_count_service INTEGER NOT NULL DEFAULT 0",
    "ALTER TABLE meta_connections ADD COLUMN IF NOT EXISTS conv_count_auth INTEGER NOT NULL DEFAULT 0",
    # Index for fast webhook routing by phone_number_id
    "CREATE INDEX IF NOT EXISTS ix_meta_conn_phone_number_id ON meta_connections (phone_number_id)",
    # Customer email for pre-payment accounts
    "ALTER TABLE accounts ADD COLUMN IF NOT EXISTS customer_email VARCHAR(255)",
    # Customer name for pre-payment accounts
    "ALTER TABLE accounts ADD COLUMN IF NOT EXISTS customer_name VARCHAR(255)",
    # Parent account for sub-tenants (agency model)
    "ALTER TABLE accounts ADD COLUMN IF NOT EXISTS parent_account_id VARCHAR(36)",
    "CREATE INDEX IF NOT EXISTS ix_accounts_parent_id ON accounts (parent_account_id)",
    # Email verification & password reset
    "ALTER TABLE users ADD COLUMN IF NOT EXISTS is_verified BOOLEAN NOT NULL DEFAULT FALSE",
    "ALTER TABLE users ADD COLUMN IF NOT EXISTS verification_token VARCHAR(255)",
    "ALTER TABLE users ADD COLUMN IF NOT EXISTS reset_token VARCHAR(255)",
    "ALTER TABLE users ADD COLUMN IF NOT EXISTS reset_token_expires TIMESTAMPTZ",
    # Lead scoring & Instagram DM
    "ALTER TABLE leads ADD COLUMN IF NOT EXISTS ig_user_id VARCHAR(100)",
    "ALTER TABLE leads ADD COLUMN IF NOT EXISTS score INTEGER",
    "ALTER TABLE leads ADD COLUMN IF NOT EXISTS score_label VARCHAR(20)",
    "ALTER TABLE leads ADD COLUMN IF NOT EXISTS score_notes TEXT",
    "ALTER TABLE leads ADD COLUMN IF NOT EXISTS last_scored_at TIMESTAMPTZ",
    "CREATE INDEX IF NOT EXISTS ix_leads_score_label ON leads (score_label)",
    # Comment -> private DM automation (growth flow)
    "ALTER TABLE automation_configs ADD COLUMN IF NOT EXISTS trigger_type VARCHAR(20) NOT NULL DEFAULT 'both'",
    "ALTER TABLE automation_configs ADD COLUMN IF NOT EXISTS media_id VARCHAR(100)",
    "ALTER TABLE automation_configs ADD COLUMN IF NOT EXISTS comment_reply_message TEXT",
    "ALTER TABLE automation_configs ADD COLUMN IF NOT EXISTS dm_message TEXT",
    "CREATE INDEX IF NOT EXISTS ix_automation_configs_media_id ON automation_configs (media_id)",

    # Conversas: bot ligado/desligado por conversa (filas bot/espera/minhas)
    "ALTER TABLE conversations ADD COLUMN IF NOT EXISTS bot_active BOOLEAN NOT NULL DEFAULT TRUE",

    # Módulos bloqueados por conta (agência-mãe controla as dependentes;
    # super admin controla qualquer conta)
    "ALTER TABLE accounts ADD COLUMN IF NOT EXISTS blocked_modules JSON",

    # WhatsApp consent (opt-in / opt-out) — required for business-initiated messages
    "ALTER TABLE leads ADD COLUMN IF NOT EXISTS whatsapp_opt_in BOOLEAN NOT NULL DEFAULT FALSE",
    "ALTER TABLE leads ADD COLUMN IF NOT EXISTS whatsapp_opt_in_at TIMESTAMPTZ",
    "ALTER TABLE leads ADD COLUMN IF NOT EXISTS whatsapp_opt_in_source VARCHAR(50)",
    "ALTER TABLE leads ADD COLUMN IF NOT EXISTS whatsapp_opted_out_at TIMESTAMPTZ",
]


@asynccontextmanager
async def lifespan(app: FastAPI):
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)
        for sql in _MIGRATIONS:
            await conn.execute(text(sql))

    scheduler_task = asyncio.create_task(_start_scheduler())

    yield

    scheduler_task.cancel()
    try:
        await scheduler_task
    except asyncio.CancelledError:
        pass
    # Graceful shutdown: cancela os timers de debounce pendentes da IA
    from app.services.ai_debounce import shutdown as ai_shutdown
    await ai_shutdown()
    await engine.dispose()


async def _start_scheduler():
    from app.services.scheduler import scheduler_loop
    await scheduler_loop()


API_DESCRIPTION = """
Multi-tenant REST API for **WhatsApp Business (Cloud API)**, **Instagram** and **Meta Ads**
management: shared inbox, automations, AI assistant, post scheduling and ad campaigns.

### Authentication
1. `POST /api/v1/auth/login` with `{"username": "...", "password": "..."}`.
2. Copy the `access_token` and click **Authorize** (top right) — paste the token only.

### Language
Error messages follow the `X-Lang` header (`en` or `pt`). If absent, `Accept-Language` is used.

### Meta platform compliance
- WhatsApp: free-form messages only inside the 24-hour customer service window; outside it,
  only approved templates to contacts that opted in. Opt-out keywords (STOP, SAIR, PARAR…)
  are honored automatically.
- Instagram: DMs only inside the 24-hour messaging window; comment → DM uses Private Replies
  (one per comment, within 7 days).
- Data deletion and deauthorization callbacks: `/api/v1/privacy/*`.
"""

OPENAPI_TAGS = [
    {"name": "auth-jwt", "description": "Login, registration, tokens and team users."},
    {"name": "auth", "description": "Meta OAuth (Facebook Login for Business) and connections."},
    {"name": "instagram", "description": "Instagram Business Login (OAuth)."},
    {"name": "instagram-api", "description": "Instagram publishing, scheduling, media, insights and DMs."},
    {"name": "whatsapp", "description": "WhatsApp Cloud API: Embedded Signup, messages, templates, broadcasts."},
    {"name": "conversations", "description": "Unified inbox conversations (WhatsApp + Instagram)."},
    {"name": "messages", "description": "Messages inside a conversation."},
    {"name": "leads", "description": "Leads / contacts, consent (opt-in) and scoring."},
    {"name": "automations", "description": "Keyword and comment → DM automations."},
    {"name": "marketing", "description": "Meta Marketing API: campaigns, ad sets, creatives, ads, insights."},
    {"name": "ai", "description": "AI customer-service assistant (Gemini + knowledge base)."},
    {"name": "webhook", "description": "Meta webhooks (signature-verified)."},
    {"name": "privacy", "description": "Privacy policy, data deletion and deauthorize callbacks."},
    {"name": "dashboard", "description": "Dashboard metrics."},
    {"name": "clients", "description": "Agency → client workspaces."},
    {"name": "payments", "description": "Subscriptions (Asaas)."},
]

app = FastAPI(
    title=f"{settings.app_name} API",
    version="1.0.0",
    description=API_DESCRIPTION,
    openapi_tags=OPENAPI_TAGS,
    contact={"name": "Destrava Sistemas", "email": "contato@destravasistemas.com.br"},
    swagger_ui_parameters={"persistAuthorization": True, "displayRequestDuration": True},
    lifespan=lifespan,
)


def _custom_openapi():
    if app.openapi_schema:
        return app.openapi_schema
    schema = get_openapi(
        title=app.title,
        version=app.version,
        description=app.description,
        routes=app.routes,
        tags=app.openapi_tags,
        contact=app.contact,
    )
    # Login is JSON (not OAuth2 form) — expose the scheme as a plain Bearer JWT
    # so the "Authorize" button in Swagger UI just takes the access token.
    schemes = schema.setdefault("components", {}).setdefault("securitySchemes", {})
    if "OAuth2PasswordBearer" in schemes:
        schemes["OAuth2PasswordBearer"] = {"type": "http", "scheme": "bearer", "bearerFormat": "JWT"}
    app.openapi_schema = schema
    return schema


app.openapi = _custom_openapi


@app.middleware("http")
async def language_middleware(request: Request, call_next):
    token = set_lang(parse_lang(request.headers.get("x-lang"), request.headers.get("accept-language")))
    try:
        return await call_next(request)
    finally:
        reset_lang(token)


@app.exception_handler(StarletteHTTPException)
async def translated_http_exception_handler(request: Request, exc: StarletteHTTPException):
    lang = parse_lang(request.headers.get("x-lang"), request.headers.get("accept-language"))
    token = set_lang(lang)
    try:
        exc.detail = translate_detail(exc.detail)
    finally:
        reset_lang(token)
    return await http_exception_handler(request, exc)

app.add_middleware(
    CORSMiddleware,
    allow_origins=settings.cors_origins_list,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


@app.get("/health", tags=["health"])
async def health():
    return {"status": "ok"}


# Guard de módulos: 403 quando a agência-mãe/super admin bloqueou o módulo do
# tenant. Aplicado nos routers 100% autenticados. O Instagram NÃO recebe guard
# de router (tem a rota pública /instagram/uploads/* que a Meta busca) — o
# bloqueio de Instagram é aplicado no frontend via /auth/me.
from fastapi import Depends as _Depends
from app.core.modules import require_module as _require_module


# Meta / legacy onboarding
app.include_router(auth.router, prefix="/api/v1")
app.include_router(webhook.router, prefix="/api/v1")
app.include_router(dashboard.router, prefix="/api/v1")
app.include_router(leads.router, prefix="/api/v1")
app.include_router(accounts.router, prefix="/api/v1")
app.include_router(automations.router, prefix="/api/v1")
app.include_router(privacy.router, prefix="/api/v1")

# JWT auth + multi-tenant chat
app.include_router(auth_jwt.router, prefix="/api/v1")
app.include_router(admin_routes.router, prefix="/api/v1")
app.include_router(conversations.router, prefix="/api/v1")
app.include_router(messages.router, prefix="/api/v1")
app.include_router(whatsapp.router, prefix="/api/v1",
                   dependencies=[_Depends(_require_module("whatsapp"))])
app.include_router(tenants.router, prefix="/api/v1")
app.include_router(payments.router)
app.include_router(clients.router, prefix="/api/v1")

# Instagram Login
app.include_router(instagram.router, prefix="/api/v1")

# Instagram API (publish, schedule, media, insights)
app.include_router(instagram_api.router, prefix="/api/v1")

# Email auth (forgot password, verify email)
app.include_router(auth_email.router, prefix="/api/v1")

# Marketing API (campaigns, ad sets, creatives, ads)
app.include_router(marketing.router, prefix="/api/v1",
                   dependencies=[_Depends(_require_module("ads"))])

# Studio de Criação (geração de vídeo com IA)
app.include_router(studio.router, prefix="/api/v1")

# IA de atendimento (Gemini + RAG): config, base de conhecimento, uso
app.include_router(ai_routes.router, prefix="/api/v1",
                   dependencies=[_Depends(_require_module("ia"))])

# WebSocket (sem prefix /api/v1 — não usa path prefix)
app.include_router(ws.router)
