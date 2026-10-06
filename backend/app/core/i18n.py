"""
Bilingual (pt-BR / en) support for API messages.

The frontend sends `X-Lang: en|pt` (or the browser `Accept-Language`). A
middleware stores the language in a ContextVar and the HTTPException handler
translates `detail` strings written in Portuguese to English when needed.

New code can call `t(pt, en)` directly.
"""
import re
from contextvars import ContextVar

DEFAULT_LANG = "pt"
SUPPORTED = ("pt", "en")

_lang: ContextVar[str] = ContextVar("lang", default=DEFAULT_LANG)


def parse_lang(x_lang: str | None, accept_language: str | None) -> str:
    for raw in (x_lang, accept_language):
        if not raw:
            continue
        code = raw.split(",")[0].strip().lower()[:2]
        if code in SUPPORTED:
            return code
    return DEFAULT_LANG


def set_lang(lang: str):
    return _lang.set(lang if lang in SUPPORTED else DEFAULT_LANG)


def get_lang() -> str:
    return _lang.get()


def t(pt: str, en: str) -> str:
    return en if get_lang() == "en" else pt


_EXACT: dict[str, str] = {
    "Token inválido.": "Invalid token.",
    "Usuário não encontrado.": "User not found.",
    "Conta não encontrada.": "Account not found.",
    "Conta não encontrada": "Account not found",
    "Token inválido ou expirado.": "Invalid or expired token.",
    "Acesso negado": "Access denied",
    "Acesso restrito.": "Restricted access.",
    "Envie um arquivo PDF.": "Please upload a PDF file.",
    "PDF excede o limite de 20 MB.": "PDF exceeds the 20 MB limit.",
    "Documento não encontrado.": "Document not found.",
    "O PDF original não está mais no servidor — envie o arquivo de novo.":
        "The original PDF is no longer on the server — please upload it again.",
    "Configure a API key da Gemini antes de ativar a IA.":
        "Set up the Gemini API key before enabling the AI.",
    "Conexão não encontrada.": "Connection not found.",
    "Plano inválido. Escolha 'autonomo' ou 'agencia'.":
        "Invalid plan. Choose 'autonomo' or 'agencia'.",
    "Nenhuma Página do Facebook encontrada. Crie uma Página primeiro.":
        "No Facebook Page found. Create a Page first.",
    "Nenhuma conta de anúncios encontrada para este usuário. Crie uma no Gerenciador de Anúncios da Meta primeiro.":
        "No ad account found for this user. Create one in Meta Ads Manager first.",
    "Token inválido ou conta já verificada.": "Invalid token or account already verified.",
    "Username já em uso.": "Username already taken.",
    "Credenciais inválidas.": "Invalid credentials.",
    "Conta desativada.": "Account disabled.",
    "Token de refresh inválido.": "Invalid refresh token.",
    "Conta não encontrada. Efetue o checkout primeiro.": "Account not found. Complete checkout first.",
    "Conta já ativada. Faça login.": "Account already activated. Please log in.",
    "Pagamento ainda não confirmado.": "Payment not confirmed yet.",
    "Apenas admins podem criar usuários.": "Only admins can create users.",
    "Role inválida. Use 'admin' ou 'agent'.": "Invalid role. Use 'admin' or 'agent'.",
    "Apenas admins podem alterar módulos.": "Only admins can change modules.",
    "Admin já tem acesso a todos os módulos.": "Admins already have access to all modules.",
    "Apenas admins podem remover usuários.": "Only admins can remove users.",
    "Você não pode remover a si mesmo.": "You cannot remove yourself.",
    "Verifique seu email para ativar o acesso — enviamos o link de confirmação.":
        "Verify your email to activate access — we sent you a confirmation link.",
    "Automação não encontrada": "Automation not found",
    "Apenas contas do tipo Agência podem gerenciar clientes.": "Only Agency accounts can manage clients.",
    "Email do dono inválido.": "Invalid owner email.",
    "Cliente não encontrado.": "Client not found.",
    "Usuário do cliente não encontrado.": "Client user not found.",
    "Apenas admins podem gerenciar módulos.": "Only admins can manage modules.",
    "Esta empresa não pertence à sua agência.": "This company does not belong to your agency.",
    "Membro não encontrado neste tenant.": "Member not found in this workspace.",
    "Apenas admins podem ver atribuições.": "Only admins can view assignments.",
    "Apenas admins podem atribuir empresas.": "Only admins can assign companies.",
    "Você não tem acesso a esta empresa. Peça ao admin para atribuí-la a você.":
        "You don't have access to this company. Ask an admin to assign it to you.",
    "Apenas admins podem iniciar conversas com template.": "Only admins can start conversations with a template.",
    "Conversa não encontrada.": "Conversation not found.",
    "Instagram não conectado. Conecte-se primeiro.": "Instagram is not connected. Connect it first.",
    "Instagram Business ID não encontrado. Informe o ig_user_id na requisição.":
        "Instagram Business ID not found. Provide ig_user_id in the request.",
    "Mídia não encontrada.": "Media not found.",
    "A data de agendamento não pode estar no passado.": "The scheduled date cannot be in the past.",
    "Agendamento não encontrado.": "Schedule not found.",
    "Instagram não conectado.": "Instagram is not connected.",
    "ID da conta Instagram Business não configurado.": "Instagram Business account ID is not configured.",
    "Erro ao descriptografar token. Reconecte o Instagram.": "Could not decrypt the token. Reconnect Instagram.",
    "Formato não suportado. Use JPEG/PNG/WebP (imagem) ou MP4/MOV (vídeo).":
        "Unsupported format. Use JPEG/PNG/WebP (image) or MP4/MOV (video).",
    "Erro ao publicar. Tente novamente.": "Publishing failed. Please try again.",
    "Erro ao listar mídias.": "Failed to list media.",
    "Erro ao buscar dados do Instagram.": "Failed to fetch Instagram data.",
    "Erro ao buscar stories.": "Failed to fetch stories.",
    "Erro ao buscar perfil": "Failed to fetch profile",
    "Apenas admins podem importar leads.": "Only admins can import leads.",
    "O CSV precisa de uma coluna de telefone (ex.: cabeçalho 'nome,telefone').":
        "The CSV needs a phone column (e.g. header 'name,phone').",
    "Lead não encontrado": "Lead not found",
    "Não é possível mesclar um lead com ele mesmo.": "A lead cannot be merged with itself.",
    "Um ou ambos os leads não foram encontrados.": "One or both leads were not found.",
    "Nenhuma conta de anúncios conectada. Conecte pelo onboarding.":
        "No ad account connected. Connect one on the Meta Connections page.",
    "Token de acesso inválido ou expirado.": "Invalid or expired access token.",
    "Conta de anúncios não configurada.": "Ad account is not configured.",
    "Nenhum campo para atualizar.": "No fields to update.",
    "Vídeo excede o limite de 300 MB.": "Video exceeds the 300 MB limit.",
    "Nenhuma conta do Instagram vinculada a uma Página do Facebook nesta conta de anúncios.":
        "No Instagram account linked to a Facebook Page in this ad account.",
    "A mensagem do anúncio é obrigatória.": "The ad message is required.",
    "Página do Facebook não configurada nesta conexão de anúncios.":
        "Facebook Page is not configured on this ads connection.",
    "Para impulsionar um post, informe o link de destino.": "To boost a post, provide the destination link.",
    "Nenhuma conta do Instagram vinculada a uma Página do Facebook.":
        "No Instagram account linked to a Facebook Page.",
    "Mensagem não encontrada.": "Message not found.",
    "Envio de mídia pelo Instagram ainda não é suportado — apenas texto.":
        "Sending media via Instagram is not supported yet — text only.",
    "Plano não encontrado": "Plan not found",
    "Use /auth/register para plano gratuito": "Use /auth/register for the free plan",
    "Email já cadastrado. Faça login.": "Email already registered. Please log in.",
    "Erro ao criar checkout": "Failed to create checkout",
    "Job não encontrado": "Job not found",
    "Instagram Business ID não encontrado.": "Instagram Business ID not found.",
    "Erro ao analisar imagem": "Failed to analyze image",
    "Erro ao gerar vídeo": "Failed to generate video",
    "Erro ao descriptografar token.": "Could not decrypt the token.",
    "Erro ao publicar no Instagram.": "Failed to publish to Instagram.",
    "Requisição de verificação inválida.": "Invalid verification request.",
    "Token de verificação inválido.": "Invalid verification token.",
    "Embedded Signup não configurado. Defina WHATSAPP_CONFIG_ID no .env (Meta App Dashboard > WhatsApp > Embedded Signup > Configurations).":
        "Embedded Signup is not configured. Set WHATSAPP_CONFIG_ID in .env (Meta App Dashboard > WhatsApp > Embedded Signup > Configurations).",
    "Apenas admins podem conectar o WhatsApp.": "Only admins can connect WhatsApp.",
    "Destinatário não identificado nesta conversa.": "Recipient not identified in this conversation.",
    "Mensagem sem wamid — não é possível reagir.": "Message has no wamid — cannot react.",
    "Apenas admins podem configurar credenciais.": "Only admins can configure credentials.",
    "Apenas admins podem sincronizar templates.": "Only admins can sync templates.",
    "Apenas admins podem criar templates.": "Only admins can create templates.",
    "Apenas admins podem deletar templates.": "Only admins can delete templates.",
    "Apenas admins podem disparar em massa.": "Only admins can send broadcasts.",
    "Conexão WhatsApp não configurada. Use PUT /whatsapp/credentials.":
        "WhatsApp connection is not configured. Connect it on the Meta Connections page.",
    "Informe de 1 a 3 botões.": "Provide 1 to 3 buttons.",
    "Lista exige button_text e ao menos uma seção.": "A list requires button_text and at least one section.",
    "Lista suporta no máximo 10 opções no total.": "A list supports at most 10 options in total.",
    "Não foi possível ler as credenciais do WhatsApp. Reconecte o número.":
        "Could not read WhatsApp credentials. Reconnect the number.",
    "Falha no upload para a Meta.": "Upload to Meta failed.",
    "Falha ao enviar mensagem interativa.": "Failed to send interactive message.",
    "Falha ao enviar reação.": "Failed to send reaction.",
    "Falha no upload do vídeo.": "Video upload failed.",
    "Erro ao criar campanha": "Failed to create campaign",
    "Erro ao atualizar campanha.": "Failed to update campaign.",
    "Erro ao excluir campanha.": "Failed to delete campaign.",
    "Erro ao duplicar campanha.": "Failed to duplicate campaign.",
    "Erro ao criar conjunto": "Failed to create ad set",
    "Erro ao atualizar conjunto.": "Failed to update ad set.",
    "Erro ao excluir conjunto.": "Failed to delete ad set.",
    "Erro ao duplicar conjunto.": "Failed to duplicate ad set.",
    "Erro ao criar criativo": "Failed to create creative",
    "Erro ao criar criativo do post": "Failed to create post creative",
    "Erro ao criar anúncio": "Failed to create ad",
    "Erro ao atualizar anúncio.": "Failed to update ad.",
    "Erro ao excluir anúncio.": "Failed to delete ad.",
    "Erro ao duplicar anúncio.": "Failed to duplicate ad.",
    "Janela de 24h expirada — o cliente não responde há mais de 24 horas. Envie um template aprovado para reabrir a conversa.":
        "24-hour window expired — the customer hasn't replied in over 24 hours. Send an approved template to reopen the conversation.",
}

_PATTERNS: list[tuple[re.Pattern, str]] = [
    (re.compile(r"^O módulo '(.+)' não está disponível para o seu usuário\. Fale com o administrador\.$"),
     "The '{0}' module is not available for your user. Contact your administrator."),
    (re.compile(r"^Módulos inválidos: (.+)$"), "Invalid modules: {0}"),
    (re.compile(r"^Empresas inválidas: (.+)$"), "Invalid companies: {0}"),
    (re.compile(r"^Arquivo excede o limite de (\d+) MB\.$"), "File exceeds the {0} MB limit."),
    (re.compile(r"^Arquivo excede o limite de (\d+) MB para (\w+)\.$"), "File exceeds the {0} MB limit for {1}."),
    (re.compile(r"^Só é possível agendar até (\d+) dias à frente\.$"), "Posts can only be scheduled up to {0} days ahead."),
    (re.compile(r"^Erro ao enviar DM: (.*)$", re.S), "Failed to send DM: {0}"),
    (re.compile(r"^Token expirado: (.*?)\. Reconecte o Instagram\.$", re.S), "Token expired: {0}. Reconnect Instagram."),
    (re.compile(r"^Token expirado: (.*)$", re.S), "Token expired: {0}"),
    (re.compile(r"^Erro ao publicar: (.*)$", re.S), "Publishing failed: {0}"),
    (re.compile(r"^Dimensão inválida\. Use: (.+)$"), "Invalid breakdown. Use: {0}"),
    (re.compile(r"^Mídia indisponível: (.*)$", re.S), "Media unavailable: {0}"),
]


def translate(text: str, lang: str | None = None) -> str:
    if (lang or get_lang()) != "en" or not isinstance(text, str):
        return text
    if text in _EXACT:
        return _EXACT[text]
    for pattern, template in _PATTERNS:
        m = pattern.match(text)
        if m:
            return template.format(*m.groups())
    return text


def translate_detail(detail):
    if isinstance(detail, str):
        return translate(detail)
    if isinstance(detail, dict) and isinstance(detail.get("message"), str):
        return {**detail, "message": translate(detail["message"])}
    return detail


def reset_lang(token) -> None:
    _lang.reset(token)
