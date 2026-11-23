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


async def send_verification_email(to: str, token: str, username: str) -> bool:
    link = f"{settings.app_url}/verify-email?token={token}"
    html = f"""
    <div style="font-family:Arial,sans-serif;max-width:480px;margin:0 auto;padding:24px">
      <h2 style="color:#1a1a2e">Confirme seu email</h2>
      <p style="color:#555">Olá {username},</p>
      <p style="color:#555">Clique no botão abaixo para confirmar seu email e ativar sua conta:</p>
      <a href="{link}" style="display:inline-block;padding:12px 32px;background:#4f46e5;color:#fff;text-decoration:none;border-radius:8px;margin:16px 0;font-size:14px">
        Confirmar Email
      </a>
      <p style="color:#999;font-size:12px">O link expira em 24 horas.</p>
    </div>
    """
    return await send_email(to, "Confirme seu email — adStudioAI", html)


async def send_new_signup_alert(brand_name: str, email: str) -> None:
    """Avisa os super admins que há um cadastro esperando aprovação."""
    from html import escape

    link = f"{settings.app_url}/app/super-admin"
    html = f"""
    <div style="font-family:Arial,sans-serif;max-width:480px;margin:0 auto;padding:24px">
      <h2 style="color:#1a1a2e">Novo cadastro para aprovar</h2>
      <p style="color:#555"><b>{escape(brand_name)}</b> ({escape(email)}) criou uma conta e está esperando liberação.</p>
      <a href="{link}" style="display:inline-block;padding:12px 32px;background:#4f46e5;color:#fff;text-decoration:none;border-radius:8px;margin:16px 0;font-size:14px">
        Abrir Super Admin
      </a>
    </div>
    """
    for admin in {e.strip().lower() for e in settings.super_admin_emails.split(",") if e.strip()}:
        await send_email(admin, f"Novo cadastro: {brand_name}", html)


async def send_account_approved_email(to: str, name: str) -> bool:
    from html import escape

    link = f"{settings.app_url}/login"
    html = f"""
    <div style="font-family:Arial,sans-serif;max-width:480px;margin:0 auto;padding:24px">
      <h2 style="color:#1a1a2e">Seu acesso foi liberado</h2>
      <p style="color:#555">Olá {escape(name)}, sua conta foi aprovada. Já pode entrar no painel.</p>
      <a href="{link}" style="display:inline-block;padding:12px 32px;background:#4f46e5;color:#fff;text-decoration:none;border-radius:8px;margin:16px 0;font-size:14px">
        Entrar
      </a>
    </div>
    """
    return await send_email(to, "Seu acesso foi liberado", html)


async def send_reset_email(to: str, token: str, username: str) -> bool:
    link = f"{settings.app_url}/reset-password?token={token}"
    html = f"""
    <div style="font-family:Arial,sans-serif;max-width:480px;margin:0 auto;padding:24px">
      <h2 style="color:#1a1a2e">Redefinir senha</h2>
      <p style="color:#555">Olá {username},</p>
      <p style="color:#555">Recebemos uma solicitação para redefinir sua senha. Clique no botão abaixo:</p>
      <a href="{link}" style="display:inline-block;padding:12px 32px;background:#4f46e5;color:#fff;text-decoration:none;border-radius:8px;margin:16px 0;font-size:14px">
        Redefinir Senha
      </a>
      <p style="color:#999;font-size:12px">Se não foi você, ignore este email. O link expira em 1 hora.</p>
    </div>
    """
    return await send_email(to, "Redefinir senha — adStudioAI", html)
