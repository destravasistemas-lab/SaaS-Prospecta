import { useNavigate, Link } from 'react-router-dom'
import {
  Inbox, Bot, BarChart3, Users, ShieldCheck, Lock, Clock, CheckCircle2,
  ArrowRight, ChevronDown, Target, Building2, MessageCircle, Camera, Megaphone,
  KeyRound, Trash2, PlugZap, Reply, Check, Layers, UserCheck, CalendarClock,
} from 'lucide-react'
import { BRANDING } from '../config/branding'
import { useI18n, LanguageToggle } from '../i18n'

const FONT = { fontFamily: "'Plus Jakarta Sans', ui-sans-serif, system-ui, sans-serif" }

function Logo({ dark = false }: { dark?: boolean }) {
  return (
    <span className="flex items-center gap-2">
      <span className="w-8 h-8 rounded-xl bg-emerald-500 flex items-center justify-center text-white font-extrabold text-sm shadow-sm">
        P
      </span>
      <span className={`font-extrabold text-lg tracking-tight ${dark ? 'text-white' : 'text-slate-900'}`}>
        {BRANDING.name}
      </span>
    </span>
  )
}

function PhoneMockup() {
  const { t } = useI18n()
  return (
    <div className="relative mx-auto w-full max-w-[340px]">
      {/* Floating card: lead source */}
      <div className="hidden sm:flex absolute -left-16 top-16 z-10 items-center gap-2.5 bg-white rounded-2xl shadow-xl shadow-slate-900/10 border border-slate-100 px-3.5 py-2.5">
        <span className="w-8 h-8 rounded-lg bg-violet-100 text-violet-600 flex items-center justify-center">
          <Megaphone size={15} />
        </span>
        <span className="text-left">
          <span className="block text-[11px] text-slate-500">{t('Novo lead', 'New lead')}</span>
          <span className="block text-xs font-bold text-slate-900">{t('Anúncio Click-to-WhatsApp', 'Click-to-WhatsApp ad')}</span>
        </span>
      </div>

      {/* Floating card: consent */}
      <div className="hidden sm:flex absolute -right-12 bottom-24 z-10 items-center gap-2 bg-white rounded-2xl shadow-xl shadow-slate-900/10 border border-slate-100 px-3.5 py-2.5">
        <CheckCircle2 size={16} className="text-emerald-500" />
        <span className="text-xs font-bold text-slate-900">{t('Opt-in registrado', 'Opt-in recorded')}</span>
      </div>

      {/* Phone */}
      <div className="rounded-[2.5rem] bg-slate-900 p-2.5 shadow-2xl shadow-emerald-900/20">
        <div className="rounded-[2rem] overflow-hidden bg-[#f4f1ea]">
          <div className="bg-emerald-600 px-4 pt-5 pb-3 flex items-center gap-3">
            <span className="w-9 h-9 rounded-full bg-white/20 flex items-center justify-center text-white font-bold text-sm">L</span>
            <span className="text-left">
              <span className="block text-white text-sm font-semibold leading-tight">Lucas Mendes</span>
              <span className="block text-emerald-100 text-[11px]">{t('online', 'online')}</span>
            </span>
          </div>
          <div className="px-3 py-4 space-y-2.5 min-h-[330px] text-[13px] text-left">
            <div className="max-w-[80%] bg-white rounded-2xl rounded-tl-sm px-3 py-2 text-slate-800 shadow-sm">
              {t('Oi! Vi o anúncio de vocês. Quanto custa o plano para agências?', 'Hi! I saw your ad. How much is the agency plan?')}
              <span className="block text-right text-[10px] text-slate-400 mt-0.5">10:02</span>
            </div>
            <div className="max-w-[85%] ml-auto bg-emerald-100 rounded-2xl rounded-tr-sm px-3 py-2 text-slate-800 shadow-sm">
              <span className="block text-[10px] font-semibold text-emerald-700 mb-0.5">{t('Assistente virtual · automatizado', 'Virtual assistant · automated')}</span>
              {t(
                'Olá, Lucas! O plano Agência inclui vários clientes em ambientes separados. Quer que eu chame um consultor?',
                'Hi Lucas! The Agency plan includes multiple clients in separate workspaces. Want me to bring in a consultant?',
              )}
              <span className="block text-right text-[10px] text-slate-400 mt-0.5">10:02</span>
            </div>
            <div className="max-w-[60%] bg-white rounded-2xl rounded-tl-sm px-3 py-2 text-slate-800 shadow-sm">
              {t('Quero sim 🙌', 'Yes please 🙌')}
              <span className="block text-right text-[10px] text-slate-400 mt-0.5">10:03</span>
            </div>
            <div className="flex justify-center">
              <span className="text-[10px] bg-white/80 text-slate-500 rounded-full px-2.5 py-1">
                {t('Ana assumiu a conversa', 'Ana took over the conversation')}
              </span>
            </div>
            <div className="max-w-[80%] ml-auto bg-emerald-100 rounded-2xl rounded-tr-sm px-3 py-2 text-slate-800 shadow-sm">
              {t('Oi Lucas, aqui é a Ana! Te mando a proposta agora 😉', "Hi Lucas, Ana here! Sending you the proposal now 😉")}
              <span className="block text-right text-[10px] text-slate-400 mt-0.5">10:04 ✓✓</span>
            </div>
          </div>
        </div>
      </div>
      <p className="text-center text-[11px] text-slate-400 mt-3">{t('Ilustração do produto', 'Product illustration')}</p>
    </div>
  )
}

export default function Landing() {
  const navigate = useNavigate()
  const { t } = useI18n()

  const channels = [
    {
      icon: MessageCircle,
      color: 'bg-emerald-100 text-emerald-700',
      name: 'WhatsApp Business',
      desc: t('Cloud API oficial, conectada pelo Cadastro Incorporado da Meta.', "Official Cloud API, connected through Meta's Embedded Signup."),
    },
    {
      icon: Camera,
      color: 'bg-pink-100 text-pink-600',
      name: 'Instagram',
      desc: t('Direct, comentários, publicação e métricas da conta profissional.', 'Direct, comments, publishing and insights for professional accounts.'),
    },
    {
      icon: Megaphone,
      color: 'bg-violet-100 text-violet-600',
      name: 'Meta Ads',
      desc: t('Campanhas, conjuntos, anúncios e leads de formulários.', 'Campaigns, ad sets, ads and lead form leads.'),
    },
  ]

  const steps = [
    { icon: PlugZap, title: t('Conecte', 'Connect'), desc: t('Entre com sua conta da Meta e escolha o que liberar. Sem senhas compartilhadas.', 'Log in with your Meta account and choose what to allow. No shared passwords.') },
    { icon: Inbox, title: t('Receba', 'Receive'), desc: t('Mensagens, comentários e leads de anúncios chegam numa fila só.', 'Messages, comments and ad leads land in a single queue.') },
    { icon: UserCheck, title: t('Atenda', 'Respond'), desc: t('O assistente faz a triagem; sua equipe assume quando precisa.', 'The assistant triages; your team takes over when needed.') },
    { icon: BarChart3, title: t('Meça', 'Measure'), desc: t('Veja quais anúncios trazem conversas e vendas de verdade.', 'See which ads bring real conversations and sales.') },
  ]

  const rules = [
    { icon: Clock, title: t('Janela de 24 horas', '24-hour window'), desc: t('Mensagens livres só enquanto a conversa está aberta pelo cliente.', 'Free-form messages only while the customer keeps the conversation open.') },
    { icon: UserCheck, title: t('Opt-in e opt-out', 'Opt-in and opt-out'), desc: t('Templates só para quem aceitou. Quem envia SAIR deixa de receber.', 'Templates only to people who agreed. Anyone who sends STOP is removed.') },
    { icon: KeyRound, title: t('Permissões mínimas', 'Minimal permissions'), desc: t('Pedimos só o que cada recurso usa, e você revoga quando quiser.', 'We only ask for what each feature uses, and you can revoke any time.') },
    { icon: Lock, title: t('Tokens criptografados', 'Encrypted tokens'), desc: t('Credenciais da Meta guardadas criptografadas e isoladas por empresa.', 'Meta credentials stored encrypted and isolated per business.') },
    { icon: Bot, title: t('IA transparente', 'Transparent AI'), desc: t('O assistente se apresenta como automatizado e chama um humano.', 'The assistant presents itself as automated and calls a human.') },
    { icon: Trash2, title: t('Exclusão de dados', 'Data deletion'), desc: t('Remover o app na Meta apaga os dados automaticamente.', 'Removing the app on Meta deletes the data automatically.') },
  ]

  const faqs = [
    {
      q: t('Preciso de um número novo de WhatsApp?', 'Do I need a new WhatsApp number?'),
      a: t(
        'Não necessariamente. Você conecta um número pela WhatsApp Business Platform no fluxo oficial da Meta. Números em uso no app WhatsApp Business podem ser migrados seguindo as regras da Meta.',
        "Not necessarily. You connect a number to the WhatsApp Business Platform through Meta's official flow. Numbers used in the WhatsApp Business app can be migrated following Meta's rules.",
      ),
    },
    {
      q: t('Posso mandar mensagem para qualquer contato?', 'Can I message any contact?'),
      a: t(
        'Você responde livremente em até 24h após a última mensagem do cliente. Fora disso, só templates aprovados pela Meta e apenas para contatos que deram opt-in.',
        "You can reply freely within 24 hours of the customer's last message. Outside that, only Meta-approved templates and only to contacts who opted in.",
      ),
    },
    {
      q: t('Quem paga as conversas do WhatsApp e os anúncios?', 'Who pays for WhatsApp conversations and ads?'),
      a: t(
        'A Meta cobra diretamente na sua conta. A assinatura do Prospecta é separada.',
        'Meta bills your account directly. The Prospecta subscription is separate.',
      ),
    },
    {
      q: t('Funciona para agências?', 'Does it work for agencies?'),
      a: t(
        'Sim. Cada cliente tem um ambiente isolado, e você alterna entre eles com um clique, controlando o que cada membro da equipe acessa.',
        'Yes. Each client has an isolated workspace, and you switch between them in one click while controlling what each team member can access.',
      ),
    },
    {
      q: t('Como removo o acesso e meus dados?', 'How do I remove access and my data?'),
      a: t(
        'Em Conexões Meta, clique em Desconectar. Ou remova o app nas configurações do Facebook/Instagram: recebemos o pedido e excluímos os dados.',
        'In Meta Connections, click Disconnect. Or remove the app in your Facebook/Instagram settings: we receive the request and delete the data.',
      ),
    },
  ]

  return (
    <div className="min-h-screen bg-white text-slate-900 antialiased overflow-x-hidden" style={FONT}>
      {/* Header */}
      <header className="sticky top-0 z-50 bg-white/85 backdrop-blur border-b border-slate-100">
        <div className="max-w-6xl mx-auto px-4 sm:px-6 h-16 flex items-center justify-between gap-4">
          <button onClick={() => navigate('/')} aria-label={BRANDING.name}>
            <Logo />
          </button>
          <nav className="hidden lg:flex items-center gap-7 text-sm font-medium text-slate-600">
            <a href="#canais" className="hover:text-slate-900">{t('Canais', 'Channels')}</a>
            <a href="#recursos" className="hover:text-slate-900">{t('Recursos', 'Features')}</a>
            <a href="#como-funciona" className="hover:text-slate-900">{t('Como funciona', 'How it works')}</a>
            <a href="#regras" className="hover:text-slate-900">{t('Segurança', 'Trust')}</a>
            <a href="#faq" className="hover:text-slate-900">FAQ</a>
            <Link to="/pricing" className="hover:text-slate-900">{t('Preços', 'Pricing')}</Link>
          </nav>
          <div className="flex items-center gap-2">
            <LanguageToggle compact light className="hidden sm:inline-flex" />
            <button onClick={() => navigate('/login')} className="hidden sm:inline px-3 py-2 text-sm font-semibold text-slate-700 hover:text-slate-900">
              {t('Entrar', 'Sign in')}
            </button>
            <button
              onClick={() => navigate('/login')}
              className="px-4 py-2 rounded-full bg-slate-900 hover:bg-slate-800 text-white text-sm font-semibold"
            >
              {t('Teste grátis', 'Free trial')}
            </button>
          </div>
        </div>
      </header>

      {/* Hero */}
      <section className="relative bg-gradient-to-b from-emerald-50/70 to-white">
        <div className="max-w-6xl mx-auto px-4 sm:px-6 pt-14 pb-20 lg:pt-20 grid lg:grid-cols-2 gap-14 items-center">
          <div className="text-left">
            <span className="inline-flex items-center gap-2 rounded-full bg-white border border-emerald-200 px-3 py-1 text-xs font-semibold text-emerald-700">
              <span className="w-1.5 h-1.5 rounded-full bg-emerald-500" />
              WhatsApp · Instagram · Meta Ads
            </span>
            <h1 className="mt-5 text-4xl sm:text-5xl lg:text-[3.4rem] font-extrabold leading-[1.08] tracking-tight text-slate-900">
              {t('Todos os leads da Meta numa', 'Every Meta lead in')}{' '}
              <span className="relative inline-block">
                <span className="relative z-10">{t('única caixa de entrada', 'one single inbox')}</span>
                <span className="absolute left-0 right-0 bottom-1 h-3 bg-emerald-200/80 -z-0 rounded" />
              </span>
            </h1>
            <p className="mt-5 text-lg text-slate-600 leading-relaxed max-w-xl">
              {t(
                'Atenda o WhatsApp e o Direct do Instagram em equipe, automatize respostas com responsabilidade e descubra quais anúncios geram vendas.',
                'Handle WhatsApp and Instagram Direct as a team, automate replies responsibly and find out which ads drive sales.',
              )}
            </p>
            <div className="mt-8 flex flex-wrap gap-3">
              <button
                onClick={() => navigate('/login')}
                className="inline-flex items-center gap-2 px-6 py-3.5 rounded-full bg-emerald-500 hover:bg-emerald-600 text-white font-bold shadow-lg shadow-emerald-500/25"
              >
                {t('Começar grátis', 'Start for free')} <ArrowRight size={18} />
              </button>
              <a
                href="#como-funciona"
                className="inline-flex items-center gap-2 px-6 py-3.5 rounded-full border border-slate-300 bg-white hover:border-slate-400 text-slate-800 font-semibold"
              >
                {t('Ver como funciona', 'See how it works')}
              </a>
            </div>
            <ul className="mt-8 grid sm:grid-cols-2 gap-x-6 gap-y-2 text-sm text-slate-600">
              {[
                t('7 dias grátis, sem cartão', '7-day free trial, no card'),
                t('Conexão oficial pela Meta', 'Official Meta connection'),
                t('Português e inglês', 'Portuguese and English'),
                t('Cancele quando quiser', 'Cancel anytime'),
              ].map((item) => (
                <li key={item} className="flex items-center gap-2">
                  <Check size={16} className="text-emerald-500 shrink-0" /> {item}
                </li>
              ))}
            </ul>
          </div>
          <PhoneMockup />
        </div>
      </section>

      {/* Channels */}
      <section id="canais" className="border-y border-slate-100 bg-slate-50/60">
        <div className="max-w-6xl mx-auto px-4 sm:px-6 py-12 grid md:grid-cols-3 gap-4">
          {channels.map((c) => {
            const Icon = c.icon
            return (
              <div key={c.name} className="flex items-start gap-4 bg-white rounded-2xl border border-slate-100 p-5">
                <span className={`w-11 h-11 rounded-xl flex items-center justify-center shrink-0 ${c.color}`}>
                  <Icon size={20} />
                </span>
                <div className="text-left">
                  <p className="font-bold text-slate-900">{c.name}</p>
                  <p className="text-sm text-slate-500 mt-1 leading-relaxed">{c.desc}</p>
                </div>
              </div>
            )
          })}
        </div>
      </section>

      {/* Features bento */}
      <section id="recursos" className="max-w-6xl mx-auto px-4 sm:px-6 py-20">
        <div className="max-w-2xl">
          <p className="text-sm font-bold text-emerald-600 uppercase tracking-wider">{t('Recursos', 'Features')}</p>
          <h2 className="mt-2 text-3xl sm:text-4xl font-extrabold tracking-tight text-slate-900">
            {t('Tudo o que a equipe comercial precisa, sem trocar de aba', 'Everything your sales team needs, without switching tabs')}
          </h2>
        </div>

        <div className="mt-10 grid md:grid-cols-6 gap-4">
          <div className="md:col-span-4 rounded-3xl bg-slate-900 text-white p-7 sm:p-8 text-left">
            <Inbox size={26} className="text-emerald-400" />
            <h3 className="mt-4 text-2xl font-bold">{t('Caixa de entrada unificada', 'Unified inbox')}</h3>
            <p className="mt-2 text-slate-300 leading-relaxed max-w-lg">
              {t(
                'WhatsApp e Instagram Direct lado a lado, com filas (bot, espera, minhas), respostas citadas, reações, mídia e indicador de janela de 24h.',
                'WhatsApp and Instagram Direct side by side, with queues (bot, waiting, mine), quoted replies, reactions, media and a 24h window indicator.',
              )}
            </p>
            <div className="mt-6 flex flex-wrap gap-2">
              {[t('Filas por atendente', 'Per-agent queues'), t('Templates aprovados', 'Approved templates'), t('Mensagens interativas', 'Interactive messages')].map((tag) => (
                <span key={tag} className="text-xs font-semibold rounded-full bg-white/10 px-3 py-1">{tag}</span>
              ))}
            </div>
          </div>

          <div className="md:col-span-2 rounded-3xl bg-emerald-50 border border-emerald-100 p-7 text-left">
            <Bot size={24} className="text-emerald-600" />
            <h3 className="mt-4 text-xl font-bold text-slate-900">{t('Assistente de IA', 'AI assistant')}</h3>
            <p className="mt-2 text-sm text-slate-600 leading-relaxed">
              {t(
                'Responde com base nos seus PDFs (catálogo, FAQ), só sobre o seu negócio, e transfere para um humano quando pedem.',
                'Answers from your PDFs (catalog, FAQ), only about your business, and hands off to a human on request.',
              )}
            </p>
          </div>

          <div className="md:col-span-2 rounded-3xl border border-slate-200 p-7 text-left">
            <Reply size={24} className="text-pink-500" />
            <h3 className="mt-4 text-xl font-bold text-slate-900">{t('Comentário → Direct', 'Comment → Direct')}</h3>
            <p className="mt-2 text-sm text-slate-600 leading-relaxed">
              {t(
                'Quem comenta a palavra-chave recebe uma resposta pública e uma resposta privada no Direct.',
                'Anyone who comments the keyword gets a public reply and one private reply in Direct.',
              )}
            </p>
          </div>

          <div className="md:col-span-2 rounded-3xl border border-slate-200 p-7 text-left">
            <CalendarClock size={24} className="text-sky-500" />
            <h3 className="mt-4 text-xl font-bold text-slate-900">{t('Publicação agendada', 'Scheduled posts')}</h3>
            <p className="mt-2 text-sm text-slate-600 leading-relaxed">
              {t(
                'Publique ou agende fotos e Reels no Instagram e acompanhe alcance e engajamento.',
                'Publish or schedule photos and Reels on Instagram and track reach and engagement.',
              )}
            </p>
          </div>

          <div className="md:col-span-2 rounded-3xl border border-slate-200 p-7 text-left">
            <Target size={24} className="text-violet-500" />
            <h3 className="mt-4 text-xl font-bold text-slate-900">{t('Atribuição por anúncio', 'Per-ad attribution')}</h3>
            <p className="mt-2 text-sm text-slate-600 leading-relaxed">
              {t(
                'Cada lead chega marcado com o anúncio de origem, de Click-to-WhatsApp a formulários.',
                'Each lead arrives tagged with its source ad, from Click-to-WhatsApp to lead forms.',
              )}
            </p>
          </div>

          <div className="md:col-span-3 rounded-3xl border border-slate-200 p-7 text-left">
            <Megaphone size={24} className="text-violet-500" />
            <h3 className="mt-4 text-xl font-bold text-slate-900">{t('Gestão de campanhas', 'Campaign management')}</h3>
            <p className="mt-2 text-sm text-slate-600 leading-relaxed">
              {t(
                'Crie campanhas, conjuntos e anúncios (imagem, vídeo, carrossel ou post), com segmentação e métricas por idade, gênero e plataforma.',
                'Create campaigns, ad sets and ads (image, video, carousel or post) with targeting and metrics by age, gender and platform.',
              )}
            </p>
          </div>

          <div className="md:col-span-3 rounded-3xl border border-slate-200 p-7 text-left">
            <Users size={24} className="text-amber-500" />
            <h3 className="mt-4 text-xl font-bold text-slate-900">{t('Equipe e permissões', 'Team and permissions')}</h3>
            <p className="mt-2 text-sm text-slate-600 leading-relaxed">
              {t(
                'Admins e agentes com acesso por módulo. Cada atendente vê só o que precisa.',
                'Admins and agents with per-module access. Each agent sees only what they need.',
              )}
            </p>
          </div>
        </div>
      </section>

      {/* How it works — timeline */}
      <section id="como-funciona" className="bg-slate-50 border-y border-slate-100">
        <div className="max-w-6xl mx-auto px-4 sm:px-6 py-20">
          <div className="text-center max-w-2xl mx-auto">
            <p className="text-sm font-bold text-emerald-600 uppercase tracking-wider">{t('Como funciona', 'How it works')}</p>
            <h2 className="mt-2 text-3xl sm:text-4xl font-extrabold tracking-tight text-slate-900">
              {t('Do primeiro clique à venda, em quatro passos', 'From first click to sale, in four steps')}
            </h2>
          </div>
          <ol className="mt-12 grid sm:grid-cols-2 lg:grid-cols-4 gap-6">
            {steps.map((s, i) => {
              const Icon = s.icon
              return (
                <li key={s.title} className="relative bg-white rounded-2xl border border-slate-200 p-6 text-left">
                  <span className="absolute -top-3 left-6 text-xs font-extrabold bg-emerald-500 text-white rounded-full px-2.5 py-0.5">
                    {String(i + 1).padStart(2, '0')}
                  </span>
                  <Icon size={22} className="text-slate-700 mt-2" />
                  <h3 className="mt-3 text-lg font-bold text-slate-900">{s.title}</h3>
                  <p className="mt-1.5 text-sm text-slate-600 leading-relaxed">{s.desc}</p>
                </li>
              )
            })}
          </ol>
        </div>
      </section>

      {/* Meta rules — dark band */}
      <section id="regras" className="bg-slate-900 text-white">
        <div className="max-w-6xl mx-auto px-4 sm:px-6 py-20 grid lg:grid-cols-3 gap-10">
          <div className="text-left">
            <ShieldCheck size={30} className="text-emerald-400" />
            <h2 className="mt-4 text-3xl font-extrabold tracking-tight">
              {t('Feito dentro das regras da Meta', "Built within Meta's rules")}
            </h2>
            <p className="mt-3 text-slate-300 leading-relaxed">
              {t(
                'Usamos apenas as APIs oficiais e aplicamos as políticas de mensagens no próprio sistema, para proteger seu número e sua conta.',
                'We only use the official APIs and enforce messaging policies inside the product, to protect your number and your account.',
              )}
            </p>
            <Link to="/privacy" className="mt-5 inline-flex items-center gap-1.5 text-sm font-semibold text-emerald-400 hover:text-emerald-300">
              {t('Ler a Política de Privacidade', 'Read the Privacy Policy')} <ArrowRight size={15} />
            </Link>
          </div>
          <div className="lg:col-span-2 grid sm:grid-cols-2 gap-4">
            {rules.map((r) => {
              const Icon = r.icon
              return (
                <div key={r.title} className="rounded-2xl bg-white/5 border border-white/10 p-5 text-left">
                  <Icon size={20} className="text-emerald-400" />
                  <p className="mt-3 font-bold">{r.title}</p>
                  <p className="mt-1 text-sm text-slate-400 leading-relaxed">{r.desc}</p>
                </div>
              )
            })}
          </div>
        </div>
      </section>

      {/* Agencies */}
      <section className="max-w-6xl mx-auto px-4 sm:px-6 py-20 grid lg:grid-cols-2 gap-12 items-center">
        <div className="order-2 lg:order-1 rounded-3xl bg-gradient-to-br from-emerald-50 to-sky-50 border border-slate-100 p-6 sm:p-8">
          <div className="space-y-3">
            {['Padaria Central', 'Studio Fit', 'Clínica Sorriso'].map((name, i) => (
              <div key={name} className="flex items-center gap-3 bg-white rounded-2xl border border-slate-100 px-4 py-3 shadow-sm">
                <span className="w-9 h-9 rounded-xl bg-slate-900 text-white flex items-center justify-center text-sm font-bold">{name.charAt(0)}</span>
                <span className="flex-1 text-left">
                  <span className="block text-sm font-bold text-slate-900">{name}</span>
                  <span className="block text-xs text-slate-500">
                    {[t('3 atendentes · WhatsApp + Instagram', '3 agents · WhatsApp + Instagram'), t('1 atendente · Instagram', '1 agent · Instagram'), t('5 atendentes · WhatsApp + Ads', '5 agents · WhatsApp + Ads')][i]}
                  </span>
                </span>
                <ArrowRight size={16} className="text-slate-400" />
              </div>
            ))}
          </div>
          <p className="text-[11px] text-slate-400 mt-3 text-center">{t('Exemplo ilustrativo', 'Illustrative example')}</p>
        </div>
        <div className="order-1 lg:order-2 text-left">
          <Building2 size={28} className="text-emerald-600" />
          <h2 className="mt-4 text-3xl sm:text-4xl font-extrabold tracking-tight text-slate-900">
            {t('Para agências: um painel, vários clientes', 'For agencies: one panel, many clients')}
          </h2>
          <p className="mt-4 text-slate-600 leading-relaxed">
            {t(
                'Crie um ambiente isolado para cada cliente, defina quais módulos ele usa e quais membros da sua equipe podem acessá-lo.',
                'Create an isolated workspace for each client, choose which modules it uses and which team members can access it.',
            )}
          </p>
          <ul className="mt-6 space-y-3 text-slate-700">
            {[
              t('Troca de cliente em um clique', 'Switch clients in one click'),
              t('Login próprio para cada cliente', 'Separate login for each client'),
              t('Módulos liberados por cliente', 'Modules enabled per client'),
              t('Visão consolidada de leads e conversão', 'Consolidated leads and conversion view'),
            ].map((item) => (
              <li key={item} className="flex items-center gap-3">
                <span className="w-6 h-6 rounded-full bg-emerald-100 text-emerald-700 flex items-center justify-center"><Check size={14} /></span>
                {item}
              </li>
            ))}
          </ul>
          <button
            onClick={() => navigate('/pricing')}
            className="mt-8 inline-flex items-center gap-2 px-6 py-3 rounded-full bg-slate-900 hover:bg-slate-800 text-white font-semibold"
          >
            <Layers size={17} /> {t('Ver planos', 'See plans')}
          </button>
        </div>
      </section>

      {/* FAQ */}
      <section id="faq" className="bg-slate-50 border-t border-slate-100">
        <div className="max-w-3xl mx-auto px-4 sm:px-6 py-20">
          <h2 className="text-3xl sm:text-4xl font-extrabold tracking-tight text-slate-900 text-center">
            {t('Perguntas frequentes', 'Frequently asked questions')}
          </h2>
          <div className="mt-10 space-y-3">
            {faqs.map((f) => (
              <details key={f.q} className="group bg-white rounded-2xl border border-slate-200 px-5 py-4 text-left">
                <summary className="flex items-center justify-between gap-4 cursor-pointer list-none font-semibold text-slate-900">
                  {f.q}
                  <ChevronDown size={18} className="text-slate-400 shrink-0 transition-transform group-open:rotate-180" />
                </summary>
                <p className="mt-3 text-sm text-slate-600 leading-relaxed">{f.a}</p>
              </details>
            ))}
          </div>
        </div>
      </section>

      {/* CTA */}
      <section className="px-4 sm:px-6 py-16">
        <div className="max-w-6xl mx-auto rounded-[2rem] bg-emerald-500 px-6 py-14 sm:px-12 text-center text-white">
          <h2 className="text-3xl sm:text-4xl font-extrabold tracking-tight">
            {t('Comece a atender melhor ainda hoje', 'Start serving customers better today')}
          </h2>
          <p className="mt-3 text-emerald-50 max-w-xl mx-auto">
            {t('Crie sua conta, conecte suas contas da Meta e responda o primeiro cliente em minutos.', 'Create your account, connect your Meta accounts and answer your first customer in minutes.')}
          </p>
          <button
            onClick={() => navigate('/login')}
            className="mt-8 inline-flex items-center gap-2 px-7 py-3.5 rounded-full bg-white text-emerald-700 font-bold hover:bg-emerald-50"
          >
            {t('Criar conta grátis', 'Create free account')} <ArrowRight size={18} />
          </button>
        </div>
      </section>

      {/* Footer */}
      <footer className="bg-slate-900 text-slate-400">
        <div className="max-w-6xl mx-auto px-4 sm:px-6 py-14 grid sm:grid-cols-2 lg:grid-cols-4 gap-10 text-sm text-left">
          <div>
            <Logo dark />
            <p className="mt-4 leading-relaxed">
              {t(
                'Atendimento e vendas pelo WhatsApp, Instagram e Meta Ads.',
                'Customer service and sales on WhatsApp, Instagram and Meta Ads.',
              )}
            </p>
            <div className="mt-4">
              <LanguageToggle compact />
            </div>
          </div>
          <div>
            <p className="font-bold text-white">{t('Produto', 'Product')}</p>
            <ul className="mt-3 space-y-2">
              <li><a href="#recursos" className="hover:text-white">{t('Recursos', 'Features')}</a></li>
              <li><a href="#como-funciona" className="hover:text-white">{t('Como funciona', 'How it works')}</a></li>
              <li><Link to="/pricing" className="hover:text-white">{t('Preços', 'Pricing')}</Link></li>
              <li><Link to="/login" className="hover:text-white">{t('Entrar', 'Sign in')}</Link></li>
            </ul>
          </div>
          <div>
            <p className="font-bold text-white">{t('Legal', 'Legal')}</p>
            <ul className="mt-3 space-y-2">
              <li><Link to="/privacy" className="hover:text-white">{t('Política de Privacidade', 'Privacy Policy')}</Link></li>
              <li><Link to="/terms" className="hover:text-white">{t('Termos de Serviço', 'Terms of Service')}</Link></li>
              <li><Link to="/data-deletion" className="hover:text-white">{t('Exclusão de Dados', 'Data Deletion')}</Link></li>
            </ul>
          </div>
          <div>
            <p className="font-bold text-white">{t('Empresa', 'Company')}</p>
            <ul className="mt-3 space-y-2">
              <li>{BRANDING.companyFullName}</li>
              <li><a href={`mailto:${BRANDING.supportEmail}`} className="hover:text-white break-all">{BRANDING.supportEmail}</a></li>
            </ul>
          </div>
        </div>
        <div className="border-t border-white/10">
          <div className="max-w-6xl mx-auto px-4 sm:px-6 py-6 text-xs space-y-1.5 text-left">
            <p>© {new Date().getFullYear()} {BRANDING.name} · {BRANDING.companyFullName}. {t('Todos os direitos reservados.', 'All rights reserved.')}</p>
            <p>
              {t(
                'Meta, Facebook, Instagram e WhatsApp são marcas da Meta Platforms, Inc. Este produto não é afiliado nem endossado pela Meta.',
                'Meta, Facebook, Instagram and WhatsApp are trademarks of Meta Platforms, Inc. This product is not affiliated with or endorsed by Meta.',
              )}
            </p>
          </div>
        </div>
      </footer>
    </div>
  )
}
