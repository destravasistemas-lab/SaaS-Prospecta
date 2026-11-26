import logging
import httpx

from app.core.config import settings

logger = logging.getLogger(__name__)

RESEND_API = "https://api.resend.com/emails"


async def send_email(to: str, subject: str, html: str) -> bool:
    if not settings.resend_api_key:
        logger.warning("Resend not configured — skipping email to %s: %s", to, subject)
        return False

    try:
        async with httpx.AsyncClient() as client:
            resp = await client.post(
                RESEND_API,
                headers={
                    "Authorization": f"Bearer {settings.resend_api_key}",
                    "Content-Type": "application/json",
                },
                json={
                    "from": f"{settings.email_from_name} <{settings.email_from}>",
                    "to": [to],
                    "subject": subject,
                    "html": html,
                },
            )
            if resp.is_success:
                logger.info("Email sent to %s: %s", to, subject)
                return True
            else:
                logger.error("Resend error [%s]: %s", resp.status_code, resp.text)
                return False
    except Exception as e:
        logger.error("Failed to send email to %s: %s", to, e)
        return False


from html import escape  # noqa: E402

BRAND = "Prospecta"


def _layout(title: str, paragraphs: list[str], button: str | None = None, link: str | None = None,
            note: str | None = None) -> str:
    """Email com a cara da marca (cabeçalho em degradê, botão, rodapé)."""
    body = "".join(f'<p style="margin:0 0 12px;color:#4b5563;font-size:15px;line-height:1.55">{p}</p>' for p in paragraphs)
    cta = (
        f'<a href="{link}" style="display:inline-block;margin:8px 0 4px;padding:13px 28px;border-radius:10px;'
        f'background:#7c3aed;background-image:linear-gradient(90deg,#7c3aed,#d946ef,#fb923c);color:#fff;'
        f'font-weight:700;font-size:14px;text-decoration:none">{button}</a>'
        if button and link else ""
    )
    small = f'<p style="margin:16px 0 0;color:#9ca3af;font-size:12px">{note}</p>' if note else ""
    return f"""
    <div style="background:#f5f3ff;padding:24px 12px;font-family:Arial,Helvetica,sans-serif">
      <div style="max-width:520px;margin:0 auto;background:#ffffff;border-radius:16px;overflow:hidden;border:1px solid #ede9fe">
        <div style="padding:18px 24px;background:#6d28d9;background-image:linear-gradient(135deg,#6d28d9,#c026d3 55%,#f97316)">
          <span style="color:#ffffff;font-weight:800;font-size:18px;letter-spacing:-0.2px">{BRAND}</span>
        </div>
        <div style="padding:28px 24px">
          <h2 style="margin:0 0 14px;color:#1f1147;font-size:20px">{title}</h2>
          {body}{cta}{small}
        </div>
        <div style="padding:14px 24px;border-top:1px solid #f3f4f6;color:#9ca3af;font-size:11px">
          {BRAND} · Destrava Sistemas
        </div>
      </div>
    </div>
    """


async def send_verification_email(to: str, token: str, username: str) -> bool:
    link = f"{settings.app_url}/verify-email?token={token}"
    html = _layout(
        "Confirme seu email",
        [f"Olá {escape(username)},", "Clique no botão abaixo para confirmar seu email e ativar sua conta."],
        "Confirmar email", link, "O link expira em 24 horas.",
    )
    return await send_email(to, f"Confirme seu email — {BRAND}", html)


async def send_new_signup_alert(brand_name: str, email: str) -> None:
    """Avisa os super admins que há um cadastro esperando aprovação."""
    link = f"{settings.app_url}/app/super-admin"
    html = _layout(
        "Novo cadastro para aprovar",
        [f"<b>{escape(brand_name)}</b> ({escape(email)}) criou uma conta e está esperando liberação."],
        "Abrir Super Admin", link,
    )
    for admin in {e.strip().lower() for e in settings.super_admin_emails.split(",") if e.strip()}:
        await send_email(admin, f"Novo cadastro: {brand_name}", html)


async def send_account_approved_email(to: str, name: str) -> bool:
    link = f"{settings.app_url}/login"
    html = _layout(
        "Seu acesso foi liberado",
        [f"Olá {escape(name)}, sua conta foi aprovada. Já pode entrar no painel.",
         f'Dica: instale o app no celular ou no computador em <a href="{settings.app_url}/instalar" '
         'style="color:#7c3aed">/instalar</a> para receber os avisos de mensagens e de leads interessados.'],
        "Entrar", link,
    )
    return await send_email(to, f"Seu acesso ao {BRAND} foi liberado", html)


async def send_reset_email(to: str, token: str, username: str) -> bool:
    link = f"{settings.app_url}/reset-password?token={token}"
    html = _layout(
        "Redefinir senha",
        [f"Olá {escape(username)},", "Recebemos um pedido para redefinir sua senha. Clique no botão abaixo:"],
        "Redefinir senha", link, "Se não foi você, ignore este email. O link expira em 1 hora.",
    )
    return await send_email(to, f"Redefinir senha — {BRAND}", html)
