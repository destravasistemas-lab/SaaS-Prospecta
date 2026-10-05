from pydantic_settings import BaseSettings
from typing import List
import json


class Settings(BaseSettings):
    app_name: str = "adStudioAI"
    debug: bool = False

    database_url: str = "postgresql+asyncpg://marketing_user:marketing_pass@localhost:5432/adstudioai"

    meta_app_id: str = ""
    meta_app_secret: str = ""
    meta_oauth_client_secret: str = ""
    meta_api_version: str = "v21.0"
    meta_redirect_uri: str = "http://localhost:8000/api/v1/auth/meta/callback"
    meta_webhook_verify_token: str = ""

    # WhatsApp Embedded Signup — Configuration ID from
    # Meta App Dashboard > WhatsApp > Embedded Signup > Configurations
    whatsapp_config_id: str = ""

    # Instagram App (Basic Display / Instagram Login)
    ig_app_id: str = ""
    ig_app_secret: str = ""
    ig_redirect_uri: str = "http://localhost:8000/api/v1/auth/instagram/callback"
    # Token de usuário gerado manualmente no painel — apenas para seed/testes locais
    ig_test_access_token: str = ""

    # Fernet key for encrypting access tokens at rest.
    # Generate: python -c "from cryptography.fernet import Fernet; print(Fernet.generate_key().decode())"
    fernet_key: str = ""

    # Optional: n8n webhook URL for event dispatching
    n8n_webhook_url: str = ""

    # ngrok (local tunnel for testing Meta webhooks)
    ngrok_authtoken: str = ""
    ngrok_domain: str = ""

    # Base pública do backend (HTTPS) — usada para montar URLs de mídia que a
    # Meta precisa buscar ao publicar posts. Em dev, é o domínio do ngrok.
    public_base_url: str = ""

    # Supabase Storage — armazena as mídias de post do Instagram fora do disco
    # (o disco do Fly é efêmero). Se vazio, cai no fallback de disco local.
    #   supabase_url:         https://<ref>.supabase.co
    #   supabase_service_key: service_role key (NÃO a anon key) — só no backend
    #   supabase_bucket:      nome do bucket PÚBLICO (a Meta precisa baixar a URL)
    supabase_url: str = ""
    supabase_service_key: str = ""
    supabase_bucket: str = "post-media"

    @property
    def storage_enabled(self) -> bool:
        return bool(self.supabase_url and self.supabase_service_key)

    # Janela máxima (em dias) para agendar um post no futuro.
    max_schedule_days: int = 15

    @property
    def public_backend_url(self) -> str:
        """URL pública do backend, com fallback para o domínio do ngrok."""
        if self.public_base_url:
            return self.public_base_url.rstrip("/")
        if self.ngrok_domain:
            return f"https://{self.ngrok_domain}"
        return "http://localhost:8000"

    secret_key: str = "change_this_to_a_random_secret_key"
    jwt_algorithm: str = "HS256"
    jwt_access_expire_minutes: int = 60
    jwt_refresh_expire_days: int = 30
    cors_origins: str = '["http://localhost:5173"]'

    # Asaas Payment Gateway
    asaas_api_key: str = ""
    asaas_mode: str = "sandbox"  # sandbox or production
    asaas_webhook_token: str = ""

    # Resend (email)
    resend_api_key: str = ""
    email_from: str = "noreply@adstudioai.com"
    email_from_name: str = "adStudioAI"
    app_url: str = "http://localhost:5173"

    # Super admins do sistema (emails separados por vírgula). Podem gerenciar
    # os módulos bloqueados de QUALQUER conta (agências e empresas).
    super_admin_emails: str = ""

    # IA (Gemini + RAG). A API key da Gemini é POR TENANT (fica no banco,
    # criptografada) — aqui só os defaults de comportamento.
    redis_url: str = ""  # ex.: redis://redis:6379/0 (vazio = fallback em memória)
    gemini_model: str = "gemini-2.5-flash"
    gemini_embedding_model: str = "text-embedding-004"
    ai_debounce_seconds: float = 3.0
    ai_request_timeout: float = 10.0
    ai_default_token_limit: int = 1_000_000  # tokens/mês incluídos por tenant

    @property
    def meta_graph_url(self) -> str:
        return f"https://graph.facebook.com/{self.meta_api_version}"

    @property
    def ig_graph_url(self) -> str:
        return f"https://graph.instagram.com/{self.meta_api_version}"

    @property
    def meta_dialog_url(self) -> str:
        return f"https://www.facebook.com/{self.meta_api_version}/dialog/oauth"

    @property
    def cors_origins_list(self) -> List[str]:
        return json.loads(self.cors_origins)

    @property
    def ig_dialog_url(self) -> str:
        return "https://www.instagram.com/oauth/authorize"

    class Config:
        env_file = ".env"
        case_sensitive = False
        # Ignora envs extras (ex.: APP_HOST/APP_PORT/UVICORN_WORKERS injetadas
        # pelo docker-compose e pelo Fly) em vez de derrubar o app na inicialização.
        extra = "ignore"


settings = Settings()
