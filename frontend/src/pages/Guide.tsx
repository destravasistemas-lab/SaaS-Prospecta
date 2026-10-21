import { useEffect, type ReactNode } from 'react'
import { Link, useLocation } from 'react-router-dom'
import {
  Rocket, Link2, MessageSquare, FileText, UserCheck, Send, Repeat, Bot, Camera, Zap,
  Inbox, Users, Megaphone, Building2, Shield, LifeBuoy, ExternalLink, ArrowRight,
  type LucideIcon,
} from 'lucide-react'
import { BRANDING } from '../config/branding'
import { useI18n, LanguageToggle } from '../i18n'

type T = (pt: string, en: string) => string

interface Section {
  id: string
  icon: LucideIcon
  title: string
  route?: string
  routeLabel?: string
  intro: string
  steps?: string[]
  rules?: string[]
  tips?: string[]
  links?: { label: string; url: string }[]
}

function sections(t: T): Section[] {
  return [
    {
      id: 'primeiros-passos',
      icon: Rocket,
      title: t('Primeiros passos', 'Getting started'),
      route: '/app',
      routeLabel: 'Dashboard',
      intro: t(
        'Em poucos minutos você cria a conta, conecta as contas da Meta e começa a atender. O Dashboard resume anúncios, Instagram, custos do WhatsApp e leads.',
        'In a few minutes you create your account, connect your Meta accounts and start serving customers. The Dashboard summarizes ads, Instagram, WhatsApp costs and leads.',
      ),
      steps: [
        t('Crie a conta em Entrar → Criar conta e escolha Autônomo (um negócio) ou Agência (vários clientes).', 'Create your account at Sign in → Sign up and choose Business (one company) or Agency (several clients).'),
        t('Vá em Conexões Meta e conecte WhatsApp, Instagram e/ou Meta Ads.', 'Go to Meta Connections and connect WhatsApp, Instagram and/or Meta Ads.'),
        t('Em Templates, sincronize ou crie seus templates do WhatsApp.', 'In Templates, sync or create your WhatsApp templates.'),
        t('Convide sua equipe em Equipe e defina o que cada pessoa acessa.', 'Invite your team in Team and set what each person can access.'),
        t('Ative as automações: palavra-chave no Instagram, IA e follow-up automático.', 'Turn on automations: Instagram keywords, AI and automatic follow-up.'),
      ],
      tips: [t('Troque o idioma (PT/EN) no rodapé do menu lateral ou em Configurações.', 'Switch the language (PT/EN) at the bottom of the side menu or in Settings.')],
    },
    {
      id: 'conexoes',
      icon: Link2,
      title: t('Conexões Meta', 'Meta Connections'),
      route: '/app/conexao',
      routeLabel: t('Abrir Conexões Meta', 'Open Meta Connections'),
      intro: t(
        'Aqui você autoriza o acesso às suas contas pelo login oficial da Meta. Nenhuma senha é compartilhada com o sistema, e cada card mostra as permissões pedidas e o motivo.',
        "Here you authorize access to your accounts through Meta's official login. No password is shared with the system, and each card shows the permissions requested and why.",
      ),
      steps: [
        t('WhatsApp: clique em Conectar e siga o Cadastro Incorporado da Meta (escolha ou crie o Business, a conta do WhatsApp Business e o número).', "WhatsApp: click Connect and follow Meta's Embedded Signup (choose or create the Business, the WhatsApp Business account and the number)."),
        t('Instagram: clique em Conectar e entre com a conta profissional do Instagram.', 'Instagram: click Connect and log in with the Instagram professional account.'),
        t('Meta Ads: clique em Conectar, entre no Facebook e autorize a conta de anúncios e a Página.', 'Meta Ads: click Connect, log in to Facebook and authorize the ad account and Page.'),
        t('Para remover, clique em Desconectar: o acesso é revogado na Meta e o token é apagado.', 'To remove, click Disconnect: access is revoked at Meta and the token is deleted.'),
      ],
      rules: [
        t('O Instagram precisa ser conta profissional (Empresa ou Criador).', 'Instagram must be a professional account (Business or Creator).'),
        t('Tokens expiram; se o status mostrar "Expirado", clique em Reconectar.', 'Tokens expire; if the status says "Expired", click Reconnect.'),
      ],
      links: [
        { label: t('Cadastro Incorporado do WhatsApp (Meta)', 'WhatsApp Embedded Signup (Meta)'), url: 'https://developers.facebook.com/docs/whatsapp/embedded-signup' },
        { label: t('API do Instagram com login do Instagram', 'Instagram API with Instagram Login'), url: 'https://developers.facebook.com/docs/instagram-platform/instagram-api-with-instagram-login' },
      ],
    },
    {
      id: 'whatsapp',
      icon: MessageSquare,
      title: t('WhatsApp — caixa de entrada', 'WhatsApp — inbox'),
      route: '/app/whatsapp',
      routeLabel: t('Abrir WhatsApp', 'Open WhatsApp'),
      intro: t(
        'Todas as conversas do número conectado, divididas em filas: Bot (o robô está atendendo), Espera (aguardando um humano) e Minhas (as que você assumiu).',
        'All conversations of the connected number, split into queues: Bot (the bot is handling it), Waiting (waiting for a human) and Mine (the ones you took over).',
      ),
      steps: [
        t('Clique numa conversa para abrir. Ao abrir, ela é marcada como lida (ticks azuis para o cliente).', 'Click a conversation to open it. Opening it marks it as read (blue ticks for the customer).'),
        t('Clique em Assumir para trazer a conversa para você; o bot é desligado nela.', 'Click Take over to bring the conversation to you; the bot is turned off for it.'),
        t('Bot ON/OFF liga ou desliga as respostas automáticas (palavra-chave e IA) só naquela conversa.', 'Bot ON/OFF turns automatic replies (keywords and AI) on or off for that conversation only.'),
        t('Passe o mouse numa mensagem para Responder (citar) ou Reagir com emoji.', 'Hover a message to Reply (quote) or React with an emoji.'),
        t('Use o clipe para enviar imagem, vídeo, áudio ou documento, e o ícone de lista para mensagens com botões ou menu.', 'Use the clip to send an image, video, audio or document, and the list icon for messages with buttons or a menu.'),
      ],
      rules: [
        t('Janela de 24h: mensagens livres só até 24h depois da última mensagem do cliente. O cabeçalho mostra o tempo restante.', "24-hour window: free-form messages only up to 24h after the customer's last message. The header shows the time left."),
        t('Fora da janela, só template aprovado — e só para contatos com opt-in (veja Consentimento).', 'Outside the window, only approved templates — and only to opted-in contacts (see Consent).'),
        t('Limites de mídia: imagem 5 MB, áudio e vídeo 16 MB, documento 100 MB.', 'Media limits: image 5 MB, audio and video 16 MB, document 100 MB.'),
      ],
      links: [
        { label: t('Política de Mensagens do WhatsApp Business', 'WhatsApp Business Messaging Policy'), url: 'https://www.whatsapp.com/legal/business-policy' },
        { label: t('WhatsApp Cloud API (documentação)', 'WhatsApp Cloud API (docs)'), url: 'https://developers.facebook.com/docs/whatsapp/cloud-api' },
      ],
    },
    {
      id: 'templates',
      icon: FileText,
      title: t('Templates do WhatsApp', 'WhatsApp templates'),
      route: '/app/templates',
      routeLabel: t('Abrir Templates', 'Open Templates'),
      intro: t(
        'Templates são mensagens pré-aprovadas pela Meta, usadas para iniciar conversas, enviar campanhas e falar fora da janela de 24h.',
        'Templates are messages pre-approved by Meta, used to start conversations, send campaigns and talk outside the 24h window.',
      ),
      steps: [
        t('Clique em Novo Template, dê um nome em snake_case (ex.: boas_vindas), escolha idioma e categoria.', 'Click New Template, give it a snake_case name (e.g. welcome_offer), choose language and category.'),
        t('Escreva o corpo; use + variável para inserir {{1}}, {{2}}… preenchidos no envio.', 'Write the body; use + variable to insert {{1}}, {{2}}… filled in when sending.'),
        t('Envie para aprovação. O status fica PENDING até a Meta aprovar (APPROVED) ou recusar (REJECTED).', 'Submit for approval. The status stays PENDING until Meta approves (APPROVED) or rejects (REJECTED).'),
        t('Clique em Sincronizar para atualizar status e trazer templates criados direto na Meta.', 'Click Sync to update statuses and bring templates created directly at Meta.'),
      ],
      rules: [
        t('Categorias: Marketing (ofertas, novidades), Utilidade (pedido, agendamento), Autenticação (códigos).', 'Categories: Marketing (offers, news), Utility (orders, appointments), Authentication (codes).'),
        t('Cada envio é cobrado pela Meta conforme a categoria; os valores na tela são estimativas.', 'Each message is billed by Meta according to its category; the amounts on screen are estimates.'),
      ],
      links: [
        { label: t('Templates de mensagem (Meta)', 'Message templates (Meta)'), url: 'https://developers.facebook.com/docs/whatsapp/business-management-api/message-templates' },
        { label: t('Preços do WhatsApp Business', 'WhatsApp Business pricing'), url: 'https://developers.facebook.com/docs/whatsapp/pricing' },
      ],
    },
    {
      id: 'consentimento',
      icon: UserCheck,
      title: t('Consentimento (opt-in e opt-out)', 'Consent (opt-in and opt-out)'),
      route: '/app/leads',
      routeLabel: t('Abrir Leads', 'Open Leads'),
      intro: t(
        'A Meta exige que mensagens iniciadas pela empresa (templates, disparos, follow-ups) só vão para quem aceitou recebê-las. O sistema registra e respeita esse consentimento.',
        'Meta requires business-initiated messages (templates, broadcasts, follow-ups) to go only to people who agreed to receive them. The system records and respects that consent.',
      ),
      steps: [
        t('Em Leads, clique em "Sem opt-in" para registrar o consentimento (data e origem ficam salvas).', 'In Leads, click "No opt-in" to record consent (date and source are saved).'),
        t('Na importação por CSV, inclua a coluna opt_in com sim/não.', 'When importing a CSV, include an opt_in column with yes/no.'),
        t('Ao enviar um template no chat, marque a confirmação de opt-in.', 'When sending a template in the chat, tick the opt-in confirmation.'),
        t('Se o cliente enviar SAIR, PARAR ou STOP, o opt-out é automático e ele recebe uma confirmação. VOLTAR ou START reativa.', 'If the customer sends STOP (or SAIR/PARAR), opt-out is automatic and they get a confirmation. START (or VOLTAR) reactivates.'),
      ],
      links: [{ label: t('Como obter opt-in (Meta)', 'Getting opt-in (Meta)'), url: 'https://developers.facebook.com/docs/whatsapp/overview/getting-opt-in' }],
    },
    {
      id: 'disparos',
      icon: Send,
      title: t('Disparos (envio para a lista)', 'Broadcasts (sending to your list)'),
      route: '/app/followups',
      routeLabel: t('Abrir Follow-ups', 'Open Follow-ups'),
      intro: t(
        'Envie um template aprovado para vários contatos de uma vez: campanhas, avisos e reativação de clientes.',
        'Send an approved template to many contacts at once: campaigns, announcements and customer win-back.',
      ),
      steps: [
        t('Em Follow-ups → Disparar, importe um CSV (nome, telefone, opt_in) ou use os leads existentes.', 'In Follow-ups → Send, import a CSV (name, phone, opt_in) or use existing leads.'),
        t('Selecione os contatos (ou todos) e clique em Disparar.', 'Select contacts (or all) and click Send.'),
        t('Escolha o template, preencha as variáveis e confirme. Ou use Templates → Disparar para enviar a toda a base com opt-in.', 'Pick the template, fill in variables and confirm. Or use Templates → Broadcast to send to your whole opted-in base.'),
        t('Acompanhe em Aguardando (sem resposta) e Responderam.', 'Track it in Awaiting reply and Replied.'),
      ],
      rules: [
        t('Só contatos com opt-in aparecem na lista; quem fez opt-out nunca recebe.', 'Only opted-in contacts appear in the list; anyone who opted out never receives it.'),
        t('Telefones no CSV são padronizados para 55DDDNÚMERO; duplicados e inválidos são ignorados.', 'Phones in the CSV are normalized to country code + area code + number; duplicates and invalid ones are skipped.'),
      ],
    },
    {
      id: 'follow-up',
      icon: Repeat,
      title: t('Follow-up automático', 'Automatic follow-up'),
      route: '/app/followups',
      routeLabel: t('Abrir Follow-ups → Automático', 'Open Follow-ups → Automatic'),
      intro: t(
        'Se o cliente não responder a um template em X dias, o sistema envia outro template aprovado — sozinho, no horário que você escolher.',
        "If the customer doesn't reply to a template within X days, the system sends another approved template — by itself, at the hours you choose.",
      ),
      steps: [
        t('Em Follow-ups → Automático → Nova regra, escolha a qual template a regra se aplica (ou qualquer um).', 'In Follow-ups → Automatic → New rule, choose which template the rule applies to (or any).'),
        t('Defina quantos dias esperar (1 a 13), o template de follow-up e as variáveis.', 'Set how many days to wait (1 to 13), the follow-up template and variables.'),
        t('Defina a janela de horário (horário de Brasília) e salve. Use a chave para pausar.', 'Set the time window (Brasília time) and save. Use the switch to pause.'),
      ],
      rules: [
        t('Só WhatsApp: no Instagram a Meta não permite mensagens após 24h sem resposta.', "WhatsApp only: on Instagram Meta doesn't allow messages after 24h without a reply."),
        t('No máximo um follow-up por envio, nunca follow-up de follow-up, só para opt-in, até 14 dias do envio original.', 'At most one follow-up per message, never a follow-up of a follow-up, opted-in only, up to 14 days after the original.'),
        t('O sistema verifica as regras a cada 10 minutos.', 'The system checks the rules every 10 minutes.'),
      ],
    },
    {
      id: 'ia',
      icon: Bot,
      title: t('Assistente de IA', 'AI assistant'),
      route: '/app/ia',
      routeLabel: t('Abrir IA & Conhecimento', 'Open AI & Knowledge'),
      intro: t(
        'Um assistente (Gemini) responde no WhatsApp com base nos documentos da sua empresa. Se ficar indisponível ou o cliente pedir uma pessoa, a conversa vai para a fila Espera.',
        'An assistant (Gemini) replies on WhatsApp based on your company documents. If it is unavailable or the customer asks for a person, the conversation goes to the Waiting queue.',
      ),
      steps: [
        t('Crie uma API key no Google AI Studio e cole em "API key da Gemini".', 'Create an API key in Google AI Studio and paste it in "Gemini API key".'),
        t('Escreva as instruções (tom de voz, o que pode e não pode dizer).', 'Write the instructions (tone of voice, what it can and cannot say).'),
        t('Envie PDFs na base de conhecimento (catálogo, FAQ, políticas, preços).', 'Upload PDFs to the knowledge base (catalog, FAQ, policies, prices).'),
        t('Ligue "IA ativa". Ela responde nas conversas com Bot ON quando nenhuma palavra-chave respondeu.', 'Turn on "AI enabled". It replies in conversations with Bot ON when no keyword replied.'),
      ],
      rules: [
        t('Regras fixas: responde só sobre o seu negócio, se identifica como automatizada quando perguntada e nunca pede senhas ou cartão.', 'Fixed rules: only answers about your business, identifies itself as automated when asked and never asks for passwords or cards.'),
        t('A cota mensal de tokens aparece em "Uso de tokens"; ao estourar, as conversas vão para a fila humana.', 'The monthly token quota is shown in "Token usage"; when exceeded, conversations go to the human queue.'),
      ],
      links: [{ label: 'Google AI Studio — API key', url: 'https://aistudio.google.com/app/apikey' }],
    },
    {
      id: 'instagram-publicar',
      icon: Camera,
      title: t('Instagram — publicar e agendar', 'Instagram — publish and schedule'),
      route: '/app/publicar',
      routeLabel: t('Abrir Publicar & Automação', 'Open Publish & Automation'),
      intro: t(
        'Publique fotos e vídeos/Reels na conta conectada, agora ou agendado, e veja as métricas da conta e das mídias.',
        'Publish photos and videos/Reels to the connected account, now or scheduled, and see account and media insights.',
      ),
      steps: [
        t('Escolha o tipo (Imagem ou Vídeo/Reel) e envie o arquivo do computador (ou cole uma URL pública).', 'Choose the type (Image or Video/Reel) and upload the file from your computer (or paste a public URL).'),
        t('Escreva a legenda e as hashtags.', 'Write the caption and hashtags.'),
        t('Clique em Publicar Agora, ou escolha data e hora e clique em Agendar.', 'Click Publish Now, or choose date and time and click Schedule.'),
        t('Acompanhe em Agendados e veja resultados em Mídias & Métricas.', 'Track it in Scheduled and see results in Media & Insights.'),
      ],
      rules: [
        t('Formatos: JPEG/PNG/WebP até 8 MB; MP4/MOV até 50 MB.', 'Formats: JPEG/PNG/WebP up to 8 MB; MP4/MOV up to 50 MB.'),
        t('Agendamento até 15 dias à frente.', 'Scheduling up to 15 days ahead.'),
      ],
      links: [{ label: t('Publicação de conteúdo (Meta)', 'Content publishing (Meta)'), url: 'https://developers.facebook.com/docs/instagram-platform/content-publishing' }],
    },
    {
      id: 'automacao-comentario',
      icon: Zap,
      title: t('Automação de comentário → Direct', 'Comment → Direct automation'),
      route: '/app/publicar',
      routeLabel: t('Abrir Publicar & Automação', 'Open Publish & Automation'),
      intro: t(
        'Quem comentar a palavra-chave no post recebe uma resposta pública e uma mensagem privada no Direct. Se responder, recebe a segunda mensagem (com o link) e a conversa passa para a equipe.',
        'Anyone who comments the keyword on the post gets a public reply and a private Direct message. If they reply, they get the second message (with the link) and the chat goes to the team.',
      ),
      steps: [
        t('Ao publicar ou agendar, ligue "Automação de comentário neste post".', 'When publishing or scheduling, turn on "Comment automation on this post".'),
        t('Defina a palavra-chave (ex.: QUERO), a resposta pública e a 1ª mensagem do Direct.', 'Set the keyword (e.g. WANT), the public reply and the 1st Direct message.'),
        t('Opcional: a 2ª mensagem com o link, enviada quando a pessoa responder.', 'Optional: the 2nd message with the link, sent when the person replies.'),
        t('Acompanhe, pause ou remova em "Automações cadastradas".', 'Track, pause or remove it in "Your automations".'),
      ],
      rules: [
        t('Variáveis: {{primeiro_nome}}, {{nome}}, {{usuario}}.', 'Variables: {{primeiro_nome}} (first name), {{nome}} (name), {{usuario}} (username).'),
        t('A Meta permite uma resposta privada por comentário, em até 7 dias.', 'Meta allows one private reply per comment, within 7 days.'),
        t('Quem comenta vira lead automaticamente, com a origem "Comentário".', 'Commenters automatically become leads, with source "Comment".'),
      ],
      links: [{ label: t('Respostas privadas (Meta)', 'Private replies (Meta)'), url: 'https://developers.facebook.com/docs/instagram-platform/private-replies' }],
    },
    {
      id: 'instagram-direct',
      icon: Inbox,
      title: t('Instagram — Direct', 'Instagram — Direct messages'),
      route: '/app/instagram-dm',
      routeLabel: t('Abrir Direct', 'Open Direct'),
      intro: t(
        'Mensagens do Instagram Direct da conta conectada, com filas Espera e Minhas, mídia recebida e reações do cliente.',
        'Instagram Direct messages of the connected account, with Waiting and Mine queues, received media and customer reactions.',
      ),
      rules: [
        t('O Instagram só permite responder até 24h após a última mensagem do cliente; depois disso a caixa de texto fica bloqueada.', "Instagram only allows replies within 24h of the customer's last message; after that the text box is locked."),
        t('Por enquanto o envio pelo sistema é só de texto.', 'For now, sending from the system is text only.'),
      ],
    },
    {
      id: 'leads',
      icon: Users,
      title: 'Leads',
      route: '/app/leads',
      routeLabel: t('Abrir Leads', 'Open Leads'),
      intro: t(
        'Todos os contatos captados por WhatsApp, Instagram (comentário e Direct) e formulários de anúncios, com origem, anúncio, score e status.',
        'All contacts captured from WhatsApp, Instagram (comments and Direct) and ad forms, with source, ad, score and status.',
      ),
      steps: [
        t('Clique em Novo lead para cadastrar um contato manualmente (nome + telefone, e-mail ou @ do Instagram). Com telefone, as mensagens desse número no WhatsApp caem no mesmo lead.', 'Click New lead to add a contact manually (name + phone, email or Instagram username). With a phone, WhatsApp messages from that number land on the same lead.'),
        t('Use a busca e os filtros por status e por score (Quentes, Mornos, Frios).', 'Use search and the status and score filters (Hot, Warm, Cold).'),
        t('Clique em Analisar Leads para calcular o score.', 'Click Score Leads to calculate the score.'),
        t('Clique no status para mudar o estágio (Novo → Contactado → Qualificado → Convertido).', 'Click the status to change the stage (New → Contacted → Qualified → Converted).'),
        t('Use Mesclar quando a mesma pessoa aparece em dois canais (Instagram e WhatsApp).', 'Use Merge when the same person appears on two channels (Instagram and WhatsApp).'),
        t('O selo "Anúncio" indica que o lead veio de um anúncio (Click-to-WhatsApp, Direct ou formulário).', 'The "Ad" badge means the lead came from an ad (Click-to-WhatsApp, Direct or form).'),
      ],
    },
    {
      id: 'campanhas',
      icon: Megaphone,
      title: t('Campanhas (Meta Ads)', 'Campaigns (Meta Ads)'),
      route: '/app/marketing',
      routeLabel: t('Abrir Campanhas', 'Open Campaigns'),
      intro: t(
        'Crie e gerencie campanhas, conjuntos e anúncios da sua conta de anúncios e veja resultados e leads por anúncio.',
        'Create and manage campaigns, ad sets and ads in your ad account and see results and leads per ad.',
      ),
      steps: [
        t('Nova Campanha: nome, objetivo e categoria especial (se aplicável). Ela é criada pausada.', 'New Campaign: name, objective and special category (if applicable). It is created paused.'),
        t('Abra a campanha → Novo conjunto: orçamento diário, otimização e segmentação (idade, gênero, países, interesses).', 'Open the campaign → New ad set: daily budget, optimization and targeting (age, gender, countries, interests).'),
        t('No conjunto → Novo anúncio: imagem, vídeo, carrossel ou um post do Instagram, com texto e link.', 'In the ad set → New ad: image, video, carousel or an Instagram post, with text and link.'),
        t('Ative, pause, duplique ou exclua pelos botões de cada item.', 'Activate, pause, duplicate or delete using each item’s buttons.'),
        t('Veja métricas, desempenho por segmento e "Leads por anúncio"; exporte os leads em CSV.', 'See metrics, performance by segment and "Leads by ad"; export leads as CSV.'),
      ],
      rules: [
        t('Anúncios de crédito, emprego, moradia, política ou jogos exigem declarar a categoria especial.', 'Ads about credit, employment, housing, politics or gambling require declaring the special category.'),
        t('O gasto é cobrado pela Meta direto na sua conta de anúncios.', 'Spend is billed by Meta directly to your ad account.'),
      ],
      links: [
        { label: t('Categorias especiais de anúncio (Meta)', 'Special ad categories (Meta)'), url: 'https://developers.facebook.com/docs/marketing-api/audiences/special-ad-category' },
        { label: t('Padrões de Publicidade da Meta', 'Meta Advertising Standards'), url: 'https://transparency.meta.com/policies/ad-standards/' },
      ],
    },
    {
      id: 'equipe',
      icon: Users,
      title: t('Equipe e permissões', 'Team and permissions'),
      route: '/app/equipe',
      routeLabel: t('Abrir Equipe', 'Open Team'),
      intro: t(
        'Adicione pessoas à conta como Admin (acesso total) ou Agente (atende conversas) e defina quais módulos cada agente vê.',
        'Add people to the account as Admin (full access) or Agent (handles conversations) and set which modules each agent sees.',
      ),
      steps: [
        t('Novo Membro: usuário, senha, nome e função.', 'New Member: username, password, name and role.'),
        t('Para agentes, escolha os módulos (WhatsApp, Instagram, Meta Ads, IA) ou deixe "Todos".', 'For agents, choose modules (WhatsApp, Instagram, Meta Ads, AI) or keep "All".'),
      ],
    },
    {
      id: 'agencias',
      icon: Building2,
      title: t('Agências e clientes', 'Agencies and clients'),
      route: '/app/clientes',
      routeLabel: t('Abrir Clientes', 'Open Clients'),
      intro: t(
        'Contas do tipo Agência criam um ambiente isolado para cada cliente, com login próprio, e alternam entre eles pelo seletor no topo do menu.',
        'Agency accounts create an isolated workspace for each client, with its own login, and switch between them using the selector at the top of the menu.',
      ),
      steps: [
        t('Novo Cliente: nome da empresa, e-mail do dono (recebe link de verificação), usuário e senha.', "New Client: company name, owner's email (gets a verification link), username and password."),
        t('Acessar abre o ambiente do cliente; volte pela opção da agência no seletor.', "Open enters the client's workspace; go back via the agency option in the selector."),
        t('Módulos libera ou bloqueia recursos por cliente; em Equipe → Empresas você define quem atende cada cliente.', 'Modules enables or blocks features per client; in Team → Companies you define who serves each client.'),
      ],
    },
    {
      id: 'privacidade',
      icon: Shield,
      title: t('Privacidade e dados', 'Privacy and data'),
      route: '/app/configuracoes',
      routeLabel: t('Abrir Configurações', 'Open Settings'),
      intro: t(
        'Tokens da Meta ficam criptografados e isolados por empresa. Você pode desconectar integrações e pedir a exclusão dos dados a qualquer momento.',
        'Meta tokens are encrypted and isolated per business. You can disconnect integrations and request data deletion at any time.',
      ),
      links: [
        { label: t('Política de Privacidade', 'Privacy Policy'), url: '/privacy' },
        { label: t('Termos de Serviço', 'Terms of Service'), url: '/terms' },
        { label: t('Exclusão de Dados', 'Data Deletion'), url: '/data-deletion' },
      ],
    },
    {
      id: 'problemas',
      icon: LifeBuoy,
      title: t('Problemas comuns', 'Troubleshooting'),
      intro: t('Mensagens que você pode ver e o que fazer.', 'Messages you may see and what to do.'),
      rules: [
        t('"Janela de 24h expirada": o cliente não escreve há mais de 24h. Envie um template (com opt-in).', '"24-hour window expired": the customer hasn\'t written in over 24h. Send a template (with opt-in).'),
        t('"Contato sem opt-in": registre o consentimento em Leads ou marque a confirmação ao enviar o template.', '"No opt-in on record": record consent in Leads or tick the confirmation when sending the template.'),
        t('"Contato pediu opt-out": a pessoa enviou SAIR/STOP. Ela só volta a receber se mandar VOLTAR/START.', '"Contact opted out": the person sent STOP. They only receive messages again if they send START.'),
        t('Template recusado: revise o texto (sem conteúdo proibido, variáveis com contexto) e envie de novo.', 'Template rejected: review the text (no prohibited content, variables with context) and submit again.'),
        t('Mensagens não chegam: confira em Conexões Meta se a conexão está "Conectado"; se expirou, reconecte.', 'Messages not arriving: check in Meta Connections that the connection says "Connected"; if it expired, reconnect.'),
      ],
    },
  ]
}

function ExternalOrInternal({ url, children }: { url: string; children: ReactNode }) {
  const cls = 'inline-flex items-center gap-1.5 text-sm text-violet-300 hover:text-violet-200 underline-offset-2 hover:underline'
  if (url.startsWith('/')) return <Link to={url} className={cls}>{children}</Link>
  return (
    <a href={url} target="_blank" rel="noopener noreferrer" className={cls}>
      {children} <ExternalLink size={12} />
    </a>
  )
}

export function GuideContent() {
  const { t } = useI18n()
  const location = useLocation()
  const list = sections(t)

  useEffect(() => {
    const id = location.hash.replace('#', '')
    if (!id) return
    const el = document.getElementById(id)
    if (el) setTimeout(() => el.scrollIntoView({ behavior: 'smooth', block: 'start' }), 50)
  }, [location.hash])

  return (
    <div className="lg:grid lg:grid-cols-[220px_1fr] lg:gap-10">
      <nav className="hidden lg:block">
        <div className="sticky top-6 space-y-0.5">
          <p className="text-[10px] font-semibold uppercase tracking-wider text-[#5a5a6e] mb-2 px-2">{t('Conteúdo', 'Contents')}</p>
          {list.map((s) => (
            <a key={s.id} href={`#${s.id}`} className="block px-2 py-1.5 rounded-lg text-[13px] text-[#8a8a9e] hover:text-white hover:bg-white/[0.04]">
              {s.title}
            </a>
          ))}
        </div>
      </nav>

      <div className="min-w-0">
        <h1 className="text-2xl sm:text-3xl font-bold text-[#e2e2e8]">{t('Guia do sistema', 'System guide')}</h1>
        <p className="text-[#8a8a9e] text-sm mt-2 max-w-2xl">
          {t(
            `Como usar cada funcionalidade do ${BRANDING.name}: onde fica, passo a passo, regras da Meta e links para saber mais.`,
            `How to use each ${BRANDING.name} feature: where it is, step by step, Meta's rules and links to learn more.`,
          )}
        </p>

        <div className="lg:hidden mt-5 flex flex-wrap gap-2">
          {list.map((s) => (
            <a key={s.id} href={`#${s.id}`} className="text-xs px-2.5 py-1 rounded-full border border-white/10 text-[#c0c0d0]">{s.title}</a>
          ))}
        </div>

        <div className="mt-8 space-y-6">
          {list.map((s) => {
            const Icon = s.icon
            return (
              <section key={s.id} id={s.id} className="scroll-mt-6 bg-[#170e2c] border border-white/[0.06] rounded-2xl p-5 sm:p-6">
                <div className="flex flex-wrap items-start justify-between gap-3">
                  <h2 className="flex items-center gap-2.5 text-lg font-semibold text-white">
                    <span className="w-9 h-9 rounded-xl bg-gradient-to-br from-violet-600 via-fuchsia-500 to-orange-400 flex items-center justify-center">
                      <Icon size={17} className="text-white" />
                    </span>
                    {s.title}
                  </h2>
                  {s.route && (
                    <Link to={s.route} className="inline-flex items-center gap-1.5 text-xs font-semibold px-3 py-1.5 rounded-lg bg-violet-600 hover:bg-violet-500 text-white">
                      {s.routeLabel} <ArrowRight size={13} />
                    </Link>
                  )}
                </div>
                <p className="mt-3 text-sm text-[#c0c0d0] leading-relaxed">{s.intro}</p>

                {s.steps && (
                  <div className="mt-4">
                    <p className="text-[11px] font-semibold uppercase tracking-wider text-[#8a8a9e] mb-2">{t('Passo a passo', 'Step by step')}</p>
                    <ol className="space-y-2">
                      {s.steps.map((step, i) => (
                        <li key={i} className="flex gap-3 text-sm text-[#d0d0e0]">
                          <span className="w-5 h-5 rounded-full bg-violet-500/20 text-violet-200 text-[11px] font-bold flex items-center justify-center shrink-0 mt-0.5">{i + 1}</span>
                          <span className="leading-relaxed">{step}</span>
                        </li>
                      ))}
                    </ol>
                  </div>
                )}

                {s.rules && (
                  <div className="mt-4 rounded-xl bg-amber-500/[0.06] border border-amber-500/20 p-4">
                    <p className="text-[11px] font-semibold uppercase tracking-wider text-amber-300/90 mb-2">
                      {s.id === 'problemas' ? t('Mensagens e soluções', 'Messages and fixes') : t('Regras e limites', 'Rules and limits')}
                    </p>
                    <ul className="space-y-1.5 list-disc list-inside text-sm text-[#d0d0e0]">
                      {s.rules.map((r, i) => <li key={i} className="leading-relaxed">{r}</li>)}
                    </ul>
                  </div>
                )}

                {s.tips && (
                  <ul className="mt-4 space-y-1 text-sm text-[#8a8a9e]">
                    {s.tips.map((tip, i) => <li key={i}>💡 {tip}</li>)}
                  </ul>
                )}

                {s.links && (
                  <div className="mt-4 flex flex-col gap-1.5">
                    <p className="text-[11px] font-semibold uppercase tracking-wider text-[#8a8a9e]">{t('Saiba mais', 'Learn more')}</p>
                    {s.links.map((l) => <ExternalOrInternal key={l.url} url={l.url}>{l.label}</ExternalOrInternal>)}
                  </div>
                )}
              </section>
            )
          })}
        </div>

        <p className="mt-8 text-xs text-[#5a5a6e]">
          {t('Não encontrou o que procurava? Escreva para', "Didn't find what you were looking for? Write to")}{' '}
          <a href={`mailto:${BRANDING.supportEmail}`} className="text-violet-300 hover:text-violet-200">{BRANDING.supportEmail}</a>
        </p>
      </div>
    </div>
  )
}

/** Dentro do painel (com menu lateral). */
export default function Guide() {
  return <GuideContent />
}

/** Versão pública em /guia (sem login). */
export function PublicGuide() {
  const { t } = useI18n()
  return (
    <div className="min-h-screen bg-[#0c0618] text-[#e2e8f0]">
      <header className="border-b border-white/[0.06]">
        <div className="max-w-6xl mx-auto px-4 sm:px-6 py-4 flex items-center justify-between gap-4">
          <Link to="/" className="flex items-center gap-2">
            <span className="w-7 h-7 rounded-lg bg-gradient-to-br from-violet-600 via-fuchsia-500 to-orange-400 flex items-center justify-center text-white font-bold text-xs">P</span>
            <span className="text-sm font-semibold text-white">{BRANDING.name}</span>
          </Link>
          <div className="flex items-center gap-3">
            <LanguageToggle compact />
            <Link to="/login" className="text-sm font-semibold text-violet-300 hover:text-violet-200">{t('Entrar', 'Sign in')}</Link>
          </div>
        </div>
      </header>
      <main className="max-w-6xl mx-auto px-4 sm:px-6 py-10">
        <GuideContent />
      </main>
    </div>
  )
}
