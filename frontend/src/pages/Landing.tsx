import { useNavigate, Link } from 'react-router-dom'
import {
  ArrowRight, ArrowDown, Bot, Check, ChevronDown, Clock, MessageCircle, Camera, Megaphone,
  Send, Zap, Target, ShieldCheck, Users, Building2, ShoppingBag, GraduationCap, Stethoscope,
  Home, Reply, Link2, UserCheck, BarChart3, Repeat, Filter, Sparkles, X,
} from 'lucide-react'
import { BRANDING } from '../config/branding'
import { useI18n, LanguageToggle } from '../i18n'

const FONT = { fontFamily: "'Plus Jakarta Sans', ui-sans-serif, system-ui, sans-serif" }
const GRADIENT = 'bg-gradient-to-r from-violet-600 via-fuchsia-500 to-orange-400'
const GRADIENT_TEXT = 'bg-gradient-to-r from-violet-600 via-fuchsia-500 to-orange-500 bg-clip-text text-transparent'

function Logo({ dark = false }: { dark?: boolean }) {
  return (
    <span className="flex items-center gap-2">
      <span className={`w-8 h-8 rounded-xl ${GRADIENT} flex items-center justify-center text-white font-extrabold text-sm shadow-md shadow-fuchsia-500/30`}>
        P
      </span>
      <span className={`font-extrabold text-lg tracking-tight ${dark ? 'text-white' : 'text-slate-900'}`}>{BRANDING.name}</span>
    </span>
  )
}

function SectionTag({ icon: Icon, children }: { icon: typeof Zap; children: string }) {
  return (
    <span className="inline-flex items-center gap-1.5 rounded-full bg-violet-100 text-violet-700 px-3 py-1 text-xs font-bold uppercase tracking-wider">
      <Icon size={13} /> {children}
    </span>
  )
}

/** Hero: post → comentário com palavra-chave → resposta + Direct automáticos. */
function KeywordFlow() {
  const { t } = useI18n()
  return (
    <div className="relative w-full max-w-md mx-auto">
      <div className="absolute -inset-6 rounded-[2.5rem] bg-gradient-to-br from-violet-200/60 via-fuchsia-200/50 to-orange-200/60 blur-2xl" aria-hidden />
      <div className="relative space-y-3">
        {/* Post */}
        <div className="bg-white rounded-3xl border border-slate-200 shadow-xl shadow-violet-900/10 overflow-hidden">
          <div className="flex items-center gap-2.5 px-4 py-3">
            <span className={`w-8 h-8 rounded-full ${GRADIENT} p-[2px]`}>
              <span className="w-full h-full rounded-full bg-white flex items-center justify-center text-[11px] font-bold text-slate-800">SF</span>
            </span>
            <span className="text-sm font-bold text-slate-900">studiofit</span>
            <span className="ml-auto text-[11px] text-slate-400">{t('Patrocinado', 'Sponsored')}</span>
          </div>
          <div className="h-32 bg-gradient-to-br from-violet-500 via-fuchsia-500 to-orange-400 flex items-center justify-center px-6 text-center">
            <p className="text-white font-extrabold text-xl leading-tight drop-shadow">
              {t('Comente QUERO e receba o desafio de 7 dias', 'Comment WANT and get the 7-day challenge')}
            </p>
          </div>
          <div className="px-4 py-3 space-y-2 text-[13px] text-left">
            <p><b>ana.lima</b> <span className="text-slate-700">{t('QUERO 🙋‍♀️', 'WANT 🙋‍♀️')}</span></p>
            <p className="pl-4 text-slate-600">
              <b className="text-slate-900">studiofit</b> {t('Te mandei no Direct, Ana! 📩', 'Sent it to your DMs, Ana! 📩')}
              <span className="ml-1.5 inline-flex items-center gap-1 text-[10px] font-semibold text-violet-600 bg-violet-50 rounded px-1.5 py-0.5">
                <Zap size={10} /> {t('automático', 'automatic')}
              </span>
            </p>
          </div>
        </div>

        <div className="flex justify-center"><ArrowDown size={20} className="text-fuchsia-500" /></div>

        {/* Direct */}
        <div className="bg-white rounded-3xl border border-slate-200 shadow-xl shadow-violet-900/10 p-4 text-left">
          <p className="text-[11px] font-semibold text-slate-400 mb-2 flex items-center gap-1.5">
            <Camera size={12} /> Instagram Direct
          </p>
          <div className="space-y-2 text-[13px]">
            <div className={`ml-auto max-w-[85%] rounded-2xl rounded-tr-sm px-3 py-2 text-white ${GRADIENT}`}>
              {t('Oi Ana! Aqui está o seu desafio 💪 Responde SIM que eu te mando o link.', "Hi Ana! Here's your challenge 💪 Reply YES and I'll send you the link.")}
            </div>
            <div className="max-w-[40%] rounded-2xl rounded-tl-sm px-3 py-2 bg-slate-100 text-slate-800">{t('SIM!', 'YES!')}</div>
            <div className={`ml-auto max-w-[85%] rounded-2xl rounded-tr-sm px-3 py-2 text-white ${GRADIENT}`}>
              {t('Perfeito! 🎉 studiofit.com/desafio — qualquer dúvida, a equipe te responde aqui.', 'Great! 🎉 studiofit.com/challenge — any questions, our team replies right here.')}
            </div>
          </div>
        </div>
      </div>
      <p className="relative text-center text-[11px] text-slate-400 mt-3">{t('Ilustração do produto', 'Product illustration')}</p>
    </div>
  )
}

function BroadcastMock() {
  const { t } = useI18n()
  const rows = [
    { label: t('Enviadas', 'Sent'), value: '1.240', w: 'w-full', c: 'bg-violet-500' },
    { label: t('Entregues', 'Delivered'), value: '1.198', w: 'w-[96%]', c: 'bg-fuchsia-500' },
    { label: t('Lidas', 'Read'), value: '903', w: 'w-[73%]', c: 'bg-orange-400' },
    { label: t('Responderam', 'Replied'), value: '214', w: 'w-[18%]', c: 'bg-emerald-500' },
  ]
  return (
    <div className="bg-white rounded-3xl border border-slate-200 shadow-xl shadow-violet-900/10 p-6 text-left">
      <div className="flex items-center justify-between">
        <p className="font-bold text-slate-900 flex items-center gap-2"><Send size={16} className="text-violet-600" /> {t('Disparo: volta_as_aulas', 'Broadcast: back_to_school')}</p>
        <span className="text-[11px] font-semibold rounded-full bg-emerald-50 text-emerald-700 px-2 py-0.5">{t('Template aprovado', 'Approved template')}</span>
      </div>
      <p className="text-xs text-slate-500 mt-1">{t('Lista: alunos 2025 · somente contatos com opt-in', 'List: 2025 students · opted-in contacts only')}</p>
      <div className="mt-5 space-y-3.5">
        {rows.map((r) => (
          <div key={r.label}>
            <div className="flex justify-between text-xs mb-1"><span className="text-slate-600">{r.label}</span><span className="font-bold text-slate-900">{r.value}</span></div>
            <div className="h-2 rounded-full bg-slate-100 overflow-hidden"><div className={`h-full rounded-full ${r.w} ${r.c}`} /></div>
          </div>
        ))}
      </div>
      <div className="mt-5 rounded-2xl bg-violet-50 px-4 py-3 text-xs text-violet-800 flex items-center gap-2">
        <Repeat size={14} /> {t('Follow-up automático para quem não respondeu em 3 dias', "Automatic follow-up for those who didn't reply in 3 days")}
      </div>
      <p className="text-[10px] text-slate-400 mt-3 text-center">{t('Números ilustrativos', 'Illustrative numbers')}</p>
    </div>
  )
}

function AdsMock() {
  const { t } = useI18n()
  const ads = [
    { name: t('Reels — Depoimento', 'Reels — Testimonial'), leads: 86, cpl: 'R$ 2,90', best: true },
    { name: t('Carrossel — Oferta', 'Carousel — Offer'), leads: 41, cpl: 'R$ 5,10', best: false },
    { name: t('Imagem — Cupom', 'Image — Coupon'), leads: 17, cpl: 'R$ 9,40', best: false },
  ]
  return (
    <div className="bg-slate-900 rounded-3xl p-6 text-left shadow-2xl shadow-violet-900/30">
      <p className="font-bold text-white flex items-center gap-2"><BarChart3 size={16} className="text-orange-400" /> {t('Leads por anúncio · 30 dias', 'Leads by ad · 30 days')}</p>
      <div className="mt-5 space-y-2.5">
        {ads.map((a) => (
          <div key={a.name} className={`flex items-center gap-3 rounded-2xl px-4 py-3 ${a.best ? 'bg-white/10 ring-1 ring-orange-400/50' : 'bg-white/5'}`}>
            <span className="flex-1 text-sm text-slate-200 truncate">{a.name}</span>
            <span className="text-sm font-bold text-white w-10 text-right">{a.leads}</span>
            <span className="text-xs text-slate-400 w-16 text-right">{a.cpl}</span>
            {a.best && <span className="text-[10px] font-bold rounded-full bg-orange-400 text-slate-900 px-2 py-0.5">{t('Melhor', 'Best')}</span>}
          </div>
        ))}
      </div>
      <div className="mt-4 flex justify-between text-[11px] text-slate-400 px-1">
        <span>{t('Anúncio', 'Ad')}</span><span>{t('Leads · custo por lead', 'Leads · cost per lead')}</span>
      </div>
      <p className="text-[10px] text-slate-500 mt-3 text-center">{t('Números ilustrativos', 'Illustrative numbers')}</p>
    </div>
  )
}

export default function Landing() {
  const navigate = useNavigate()
  const { t } = useI18n()
  const goSignup = () => navigate('/login')

  const engines = [
    { icon: Zap, title: t('Automação', 'Automation'), desc: t('Comentário vira Direct, Direct vira lead, lead vira atendimento — no automático.', 'Comments become DMs, DMs become leads, leads become conversations — automatically.'), href: '#automacao' },
    { icon: Send, title: t('Disparos', 'Broadcasts'), desc: t('Templates no WhatsApp para sua lista com opt-in, com follow-up de quem não respondeu.', "WhatsApp templates to your opted-in list, with follow-up for those who didn't reply."), href: '#disparos' },
    { icon: Megaphone, title: t('Tráfego', 'Paid traffic'), desc: t('Crie e gerencie campanhas e veja quais anúncios trazem lead de verdade.', 'Create and manage campaigns and see which ads bring real leads.'), href: '#trafego' },
  ]

  const useCases = [
    { icon: GraduationCap, title: t('Infoprodutos e lançamentos', 'Info products and launches'), desc: t('Comente a palavra e receba a aula, o e-book ou o link do checkout.', 'Comment the word and get the class, the e-book or the checkout link.') },
    { icon: ShoppingBag, title: t('E-commerce', 'E-commerce'), desc: t('Cupom no Direct, catálogo no WhatsApp e recuperação de interessados.', 'Coupon in DMs, catalog on WhatsApp and follow-up with interested buyers.') },
    { icon: Stethoscope, title: t('Clínicas e serviços', 'Clinics and services'), desc: t('Triagem automática, perguntas frequentes e agendamento com a equipe.', 'Automatic triage, FAQs and scheduling with your team.') },
    { icon: Home, title: t('Imobiliárias', 'Real estate'), desc: t('Lead do anúncio cai direto no WhatsApp do corretor certo.', 'Ad leads go straight to the right agent on WhatsApp.') },
    { icon: Building2, title: t('Agências', 'Agencies'), desc: t('Um painel para todos os clientes, com tráfego e atendimento juntos.', 'One panel for all clients, with traffic and service together.') },
  ]

  const before = [
    t('Comentários sem resposta e Direct lotado', 'Unanswered comments and a flooded inbox'),
    t('Lead do anúncio esfria esperando atendimento', 'Ad leads go cold waiting for a reply'),
    t('Disparos por celular pessoal, com risco de bloqueio', 'Broadcasts from personal phones, with ban risk'),
    t('Não sabe qual anúncio gerou venda', "No idea which ad drove the sale"),
    t('Cada atendente num aparelho diferente', 'Each agent on a different device'),
  ]
  const after = [
    t('Resposta e Direct automáticos por palavra-chave', 'Automatic reply and DM by keyword'),
    t('Assistente responde na hora e passa para a equipe', 'Assistant replies instantly and hands off to the team'),
    t('Disparos pela API oficial, só para quem aceitou', 'Broadcasts via the official API, only to people who agreed'),
    t('Leads e conversas marcados com o anúncio de origem', 'Leads and chats tagged with their source ad'),
    t('Equipe inteira numa caixa de entrada com filas', 'Whole team in one inbox with queues'),
  ]

  const faqs = [
    {
      q: t('Como funciona a automação por palavra-chave?', 'How does keyword automation work?'),
      a: t(
        'Você escolhe o post e a palavra (ex.: QUERO). Quem comentar recebe uma resposta pública e uma mensagem privada no Direct. Se a pessoa responder, o sistema envia a segunda mensagem com o link e passa a conversa para sua equipe.',
        'You pick the post and the word (e.g. WANT). Anyone who comments gets a public reply and a private Direct message. If they reply, the system sends the second message with the link and hands the chat to your team.',
      ),
    },
    {
      q: t('Posso disparar mensagens para minha lista no WhatsApp?', 'Can I send broadcasts to my WhatsApp list?'),
      a: t(
        'Sim, com templates aprovados pela Meta e apenas para contatos que aceitaram receber (opt-in). Quem responde SAIR é removido automaticamente. Isso protege a qualidade e a reputação do seu número.',
        'Yes, with Meta-approved templates and only to contacts who agreed to receive them (opt-in). Anyone who replies STOP is removed automatically. This protects the quality and reputation of your number.',
      ),
    },
    {
      q: t('Como funciona o follow-up automático?', 'How does automatic follow-up work?'),
      a: t(
        'Você define: se o cliente não responder a um template em X dias, o sistema envia outro template aprovado, uma única vez e só no horário escolhido. Funciona no WhatsApp; no Instagram a Meta não permite mensagens depois de 24h sem resposta.',
        "You set it up: if the customer doesn't reply to a template within X days, the system sends another approved template, only once and only during the hours you choose. It works on WhatsApp; on Instagram Meta doesn't allow messages after 24 hours without a reply.",
      ),
    },
    {
      q: t('Preciso deixar o celular ligado?', 'Do I need to keep my phone on?'),
      a: t(
        'Não. A conexão é feita pela WhatsApp Cloud API oficial, sem QR code e sem depender de aparelho.',
        'No. The connection uses the official WhatsApp Cloud API, with no QR code and no device dependency.',
      ),
    },
    {
      q: t('Consigo criar campanhas por aqui?', 'Can I create campaigns here?'),
      a: t(
        'Sim. Você cria campanhas, conjuntos e anúncios (imagem, vídeo, carrossel ou post do Instagram), pausa, duplica e acompanha os resultados e os leads de cada anúncio.',
        'Yes. You create campaigns, ad sets and ads (image, video, carousel or Instagram post), pause, duplicate and track results and leads for each ad.',
      ),
    },
    {
      q: t('Quem paga as mensagens e os anúncios?', 'Who pays for messages and ads?'),
      a: t('A Meta cobra direto na sua conta. A assinatura do Prospecta é separada.', 'Meta bills your account directly. The Prospecta subscription is separate.'),
    },
  ]

  return (
    <div className="min-h-screen bg-white text-slate-900 antialiased overflow-x-hidden" style={FONT}>
      {/* Header */}
      <header className="sticky top-0 z-50 bg-white/85 backdrop-blur border-b border-slate-100">
        <div className="max-w-6xl mx-auto px-4 sm:px-6 h-16 flex items-center justify-between gap-4">
          <button onClick={() => navigate('/')} aria-label={BRANDING.name}><Logo /></button>
          <nav className="hidden lg:flex items-center gap-7 text-sm font-semibold text-slate-600">
            <a href="#automacao" className="hover:text-violet-700">{t('Automação', 'Automation')}</a>
            <a href="#disparos" className="hover:text-violet-700">{t('Disparos', 'Broadcasts')}</a>
            <a href="#trafego" className="hover:text-violet-700">{t('Tráfego', 'Traffic')}</a>
            <a href="#ia" className="hover:text-violet-700">{t('IA', 'AI')}</a>
            <a href="#faq" className="hover:text-violet-700">FAQ</a>
            <Link to="/pricing" className="hover:text-violet-700">{t('Preços', 'Pricing')}</Link>
          </nav>
          <div className="flex items-center gap-2">
            <LanguageToggle compact light className="hidden sm:inline-flex" />
            <button onClick={() => navigate('/login')} className="hidden sm:inline px-3 py-2 text-sm font-semibold text-slate-700 hover:text-slate-900">
              {t('Entrar', 'Sign in')}
            </button>
            <button onClick={goSignup} className="px-4 py-2 rounded-full bg-violet-600 hover:bg-violet-700 text-white text-sm font-bold">
              {t('Começar grátis', 'Start free')}
            </button>
          </div>
        </div>
      </header>

      {/* Hero */}
      <section className="relative">
        <div className="absolute inset-x-0 top-0 h-[520px] bg-gradient-to-b from-violet-50 via-fuchsia-50/40 to-white" aria-hidden />
        <div className="relative max-w-6xl mx-auto px-4 sm:px-6 pt-14 pb-20 lg:pt-20 grid lg:grid-cols-[1.1fr_1fr] gap-14 items-center">
          <div className="text-left">
            <span className="inline-flex items-center gap-2 rounded-full bg-white border border-violet-200 px-3 py-1 text-xs font-bold text-violet-700 shadow-sm">
              <Sparkles size={13} /> {t('Automação · Disparos · Tráfego', 'Automation · Broadcasts · Traffic')}
            </span>
            <h1 className="mt-5 text-4xl sm:text-5xl lg:text-[3.5rem] font-extrabold leading-[1.05] tracking-tight">
              {t('Transforme comentários e anúncios em', 'Turn comments and ads into')}{' '}
              <span className={GRADIENT_TEXT}>{t('vendas no automático', 'sales on autopilot')}</span>
            </h1>
            <p className="mt-5 text-lg text-slate-600 leading-relaxed max-w-xl">
              {t(
                'Automatize o Direct por palavra-chave, dispare campanhas no WhatsApp para sua lista e rode tráfego sabendo exatamente qual anúncio vende — tudo num painel só.',
                'Automate Instagram DMs by keyword, send WhatsApp broadcasts to your list and run paid traffic knowing exactly which ad sells — all in one panel.',
              )}
            </p>
            <div className="mt-8 flex flex-wrap gap-3">
              <button onClick={goSignup} className={`inline-flex items-center gap-2 px-6 py-3.5 rounded-full text-white font-bold shadow-lg shadow-fuchsia-500/30 hover:brightness-110 ${GRADIENT}`}>
                {t('Criar minha automação', 'Build my automation')} <ArrowRight size={18} />
              </button>
              <a href="#automacao" className="inline-flex items-center gap-2 px-6 py-3.5 rounded-full border border-slate-300 bg-white hover:border-violet-400 text-slate-800 font-semibold">
                {t('Ver como funciona', 'See how it works')}
              </a>
            </div>
            <div className="mt-8 flex flex-wrap gap-x-6 gap-y-2 text-sm text-slate-600">
              {[t('7 dias grátis', '7-day free trial'), t('Sem cartão de crédito', 'No credit card'), t('APIs oficiais da Meta', 'Official Meta APIs')].map((item) => (
                <span key={item} className="flex items-center gap-1.5"><Check size={16} className="text-violet-600" /> {item}</span>
              ))}
            </div>
          </div>
          <KeywordFlow />
        </div>
      </section>

      {/* 3 engines */}
      <section className="max-w-6xl mx-auto px-4 sm:px-6 -mt-4 pb-6">
        <div className="grid md:grid-cols-3 gap-4">
          {engines.map((e) => {
            const Icon = e.icon
            return (
              <a key={e.title} href={e.href} className="group rounded-3xl border border-slate-200 bg-white p-6 text-left hover:border-violet-300 hover:shadow-lg hover:shadow-violet-900/5 transition-all">
                <span className={`w-11 h-11 rounded-2xl ${GRADIENT} text-white flex items-center justify-center`}><Icon size={20} /></span>
                <p className="mt-4 text-lg font-extrabold">{e.title}</p>
                <p className="mt-1.5 text-sm text-slate-600 leading-relaxed">{e.desc}</p>
                <span className="mt-4 inline-flex items-center gap-1 text-sm font-bold text-violet-700 group-hover:gap-2 transition-all">
                  {t('Saiba mais', 'Learn more')} <ArrowRight size={15} />
                </span>
              </a>
            )
          })}
        </div>
      </section>

      {/* Automation */}
      <section id="automacao" className="max-w-6xl mx-auto px-4 sm:px-6 py-20">
        <div className="max-w-3xl">
          <SectionTag icon={Zap}>{t('Automação de Direct', 'DM automation')}</SectionTag>
          <h2 className="mt-4 text-3xl sm:text-[2.6rem] font-extrabold tracking-tight leading-tight">
            {t('Cada comentário com a palavra-chave vira uma conversa no Direct', 'Every comment with the keyword becomes a Direct conversation')}
          </h2>
          <p className="mt-4 text-lg text-slate-600">
            {t(
                'Configure em um minuto ao publicar o post. O Prospecta responde, entrega o conteúdo e chama sua equipe na hora certa.',
                'Set it up in a minute when publishing the post. Prospecta replies, delivers the content and calls your team at the right time.',
            )}
          </p>
        </div>

        <div className="mt-12 grid sm:grid-cols-2 lg:grid-cols-4 gap-4">
          {[
            { icon: MessageCircle, n: '1', title: t('A pessoa comenta', 'They comment'), desc: t('Ex.: "QUERO" no post ou no anúncio.', 'E.g. "WANT" on the post or ad.') },
            { icon: Reply, n: '2', title: t('Resposta pública', 'Public reply'), desc: t('"Te mandei no Direct, Ana!" — com o nome dela.', '"Sent it to your DMs, Ana!" — with her name.') },
            { icon: Send, n: '3', title: t('Mensagem no Direct', 'Direct message'), desc: t('Uma resposta privada com o gancho da oferta.', 'One private reply with the offer hook.') },
            { icon: Link2, n: '4', title: t('Link + atendente', 'Link + agent'), desc: t('Ela responde, recebe o link e a equipe assume.', 'She replies, gets the link and the team takes over.') },
          ].map((s) => {
            const Icon = s.icon
            return (
              <div key={s.n} className="relative rounded-3xl bg-slate-50 border border-slate-100 p-6 text-left">
                <span className="absolute top-5 right-5 text-4xl font-extrabold text-violet-100">{s.n}</span>
                <Icon size={22} className="text-violet-600" />
                <p className="mt-4 font-extrabold text-slate-900">{s.title}</p>
                <p className="mt-1.5 text-sm text-slate-600 leading-relaxed">{s.desc}</p>
              </div>
            )
          })}
        </div>

        <div className="mt-8 grid md:grid-cols-3 gap-4">
          {[
            { title: t('Responde em segundos, 24h por dia', 'Replies in seconds, 24/7'), desc: t('Ninguém fica esperando — nem de madrugada, nem no fim de semana.', 'Nobody waits — not at night, not on weekends.') },
            { title: t('Personalizado com o nome', 'Personalized with the name'), desc: t('Variáveis como {{primeiro_nome}} deixam a mensagem humana.', "Name variables ({{primeiro_nome}}) keep the message human.") },
            { title: t('Vira lead automaticamente', 'Becomes a lead automatically'), desc: t('Quem comenta entra na lista de leads com a origem marcada.', 'Commenters join your lead list with the source tagged.') },
          ].map((b) => (
            <div key={b.title} className="flex gap-3 text-left">
              <span className="mt-0.5 w-6 h-6 rounded-full bg-violet-600 text-white flex items-center justify-center shrink-0"><Check size={14} /></span>
              <div>
                <p className="font-bold text-slate-900">{b.title}</p>
                <p className="text-sm text-slate-600 mt-1">{b.desc}</p>
              </div>
            </div>
          ))}
        </div>
      </section>

      {/* Broadcasts */}
      <section id="disparos" className="bg-gradient-to-b from-violet-50/60 to-white border-y border-violet-100/60">
        <div className="max-w-6xl mx-auto px-4 sm:px-6 py-20 grid lg:grid-cols-2 gap-14 items-center">
          <div className="text-left">
            <SectionTag icon={Send}>{t('Disparos no WhatsApp', 'WhatsApp broadcasts')}</SectionTag>
            <h2 className="mt-4 text-3xl sm:text-[2.6rem] font-extrabold tracking-tight leading-tight">
              {t('Fale com toda a sua lista sem arriscar o número', 'Reach your whole list without risking your number')}
            </h2>
            <p className="mt-4 text-lg text-slate-600">
              {t(
                'Campanhas, avisos e reativação de clientes com templates aprovados pela Meta, enviados pela API oficial para quem aceitou receber.',
                'Campaigns, announcements and customer win-back with Meta-approved templates, sent via the official API to people who agreed to receive them.',
              )}
            </p>
            <ul className="mt-7 space-y-3.5">
              {[
                { icon: Filter, text: t('Importe sua lista por CSV e escolha quem recebe', 'Import your list via CSV and choose who receives it') },
                { icon: UserCheck, text: t('Opt-in registrado e opt-out automático (SAIR/STOP)', 'Recorded opt-in and automatic opt-out (STOP)') },
                { icon: Repeat, text: t('Follow-up automático para quem não respondeu, no horário que você escolher', "Automatic follow-up for those who didn't reply, at the hours you choose") },
                { icon: MessageCircle, text: t('Respostas caem na caixa de entrada da equipe', "Replies land in the team's inbox") },
              ].map((item) => {
                const Icon = item.icon
                return (
                  <li key={item.text} className="flex items-center gap-3 text-slate-700">
                    <span className="w-9 h-9 rounded-xl bg-white border border-violet-100 text-violet-600 flex items-center justify-center shrink-0"><Icon size={17} /></span>
                    {item.text}
                  </li>
                )
              })}
            </ul>
          </div>
          <BroadcastMock />
        </div>
      </section>

      {/* Traffic */}
      <section id="trafego" className="max-w-6xl mx-auto px-4 sm:px-6 py-20 grid lg:grid-cols-2 gap-14 items-center">
        <div className="order-2 lg:order-1"><AdsMock /></div>
        <div className="order-1 lg:order-2 text-left">
          <SectionTag icon={Target}>{t('Tráfego pago', 'Paid traffic')}</SectionTag>
          <h2 className="mt-4 text-3xl sm:text-[2.6rem] font-extrabold tracking-tight leading-tight">
            {t('Rode tráfego e saiba qual anúncio traz cliente', 'Run ads and know which one brings customers')}
          </h2>
          <p className="mt-4 text-lg text-slate-600">
            {t(
              'Crie e gerencie campanhas do Meta Ads no mesmo lugar onde você atende. Cada lead chega marcado com o anúncio que o trouxe.',
              'Create and manage Meta Ads campaigns in the same place you serve customers. Every lead arrives tagged with the ad that brought it.',
            )}
          </p>
          <div className="mt-7 grid sm:grid-cols-2 gap-3">
            {[
              t('Campanhas, conjuntos e anúncios', 'Campaigns, ad sets and ads'),
              t('Imagem, vídeo, carrossel ou post', 'Image, video, carousel or post'),
              t('Click-to-WhatsApp e Lead Ads', 'Click-to-WhatsApp and Lead Ads'),
              t('Custo por lead e ROAS', 'Cost per lead and ROAS'),
              t('Resultados por idade, gênero, plataforma', 'Results by age, gender, platform'),
              t('Pausar, duplicar e ajustar orçamento', 'Pause, duplicate and adjust budget'),
            ].map((f) => (
              <span key={f} className="flex items-center gap-2 text-sm text-slate-700">
                <Check size={16} className="text-orange-500 shrink-0" /> {f}
              </span>
            ))}
          </div>
        </div>
      </section>

      {/* AI */}
      <section id="ia" className="bg-[#140b2e] text-white">
        <div className="max-w-6xl mx-auto px-4 sm:px-6 py-20 grid lg:grid-cols-2 gap-12 items-center">
          <div className="text-left">
            <span className="inline-flex items-center gap-1.5 rounded-full bg-white/10 text-fuchsia-200 px-3 py-1 text-xs font-bold uppercase tracking-wider">
              <Bot size={13} /> {t('Assistente de IA', 'AI assistant')}
            </span>
            <h2 className="mt-4 text-3xl sm:text-[2.6rem] font-extrabold tracking-tight leading-tight">
              {t('Um atendente que conhece seu negócio e nunca dorme', 'An agent who knows your business and never sleeps')}
            </h2>
            <p className="mt-4 text-lg text-violet-200/80">
              {t(
                'Envie seu catálogo, tabela de preços e FAQ em PDF. O assistente responde no WhatsApp com base neles e chama sua equipe quando o cliente quer falar com uma pessoa.',
                'Upload your catalog, price list and FAQ as PDFs. The assistant answers on WhatsApp based on them and calls your team when the customer wants a person.',
              )}
            </p>
          </div>
          <div className="grid sm:grid-cols-2 gap-4">
            {[
              { icon: Clock, title: t('Responde na hora', 'Instant replies'), desc: t('Qualifica o lead enquanto ele está interessado.', 'Qualifies the lead while they are interested.') },
              { icon: UserCheck, title: t('Passa para humano', 'Hands off to humans'), desc: t('Fila de espera para a equipe assumir.', 'Waiting queue for your team to take over.') },
              { icon: ShieldCheck, title: t('Só fala do seu negócio', 'Stays on topic'), desc: t('E se apresenta como assistente automatizado.', 'And presents itself as an automated assistant.') },
              { icon: Users, title: t('Funciona com a equipe', 'Works with your team'), desc: t('Liga e desliga o bot por conversa.', 'Turn the bot on or off per conversation.') },
            ].map((c) => {
              const Icon = c.icon
              return (
                <div key={c.title} className="rounded-3xl bg-white/5 border border-white/10 p-5 text-left">
                  <Icon size={20} className="text-orange-300" />
                  <p className="mt-3 font-bold">{c.title}</p>
                  <p className="mt-1 text-sm text-violet-200/70">{c.desc}</p>
                </div>
              )
            })}
          </div>
        </div>
      </section>

      {/* Use cases */}
      <section className="max-w-6xl mx-auto px-4 sm:px-6 py-20">
        <div className="text-center max-w-2xl mx-auto">
          <h2 className="text-3xl sm:text-[2.6rem] font-extrabold tracking-tight leading-tight">
            {t('Feito para quem vende pelo Instagram e WhatsApp', 'Built for businesses that sell on Instagram and WhatsApp')}
          </h2>
        </div>
        <div className="mt-12 grid sm:grid-cols-2 lg:grid-cols-5 gap-4">
          {useCases.map((u) => {
            const Icon = u.icon
            return (
              <div key={u.title} className="rounded-3xl border border-slate-200 p-5 text-left hover:border-violet-300 transition-colors">
                <Icon size={22} className="text-fuchsia-500" />
                <p className="mt-3 font-extrabold text-slate-900 leading-snug">{u.title}</p>
                <p className="mt-1.5 text-sm text-slate-600 leading-relaxed">{u.desc}</p>
              </div>
            )
          })}
        </div>
      </section>

      {/* Before / after */}
      <section className="max-w-6xl mx-auto px-4 sm:px-6 pb-20">
        <div className="grid md:grid-cols-2 gap-4">
          <div className="rounded-3xl bg-slate-50 border border-slate-200 p-7 text-left">
            <p className="text-sm font-bold text-slate-500 uppercase tracking-wider">{t('Sem o Prospecta', 'Without Prospecta')}</p>
            <ul className="mt-5 space-y-3">
              {before.map((b) => (
                <li key={b} className="flex items-start gap-3 text-slate-600">
                  <span className="mt-0.5 w-6 h-6 rounded-full bg-slate-200 text-slate-500 flex items-center justify-center shrink-0"><X size={13} /></span>
                  {b}
                </li>
              ))}
            </ul>
          </div>
          <div className={`rounded-3xl p-[2px] ${GRADIENT}`}>
            <div className="h-full rounded-[calc(1.5rem-2px)] bg-white p-7 text-left">
              <p className={`text-sm font-bold uppercase tracking-wider ${GRADIENT_TEXT}`}>{t('Com o Prospecta', 'With Prospecta')}</p>
              <ul className="mt-5 space-y-3">
                {after.map((a) => (
                  <li key={a} className="flex items-start gap-3 text-slate-800 font-medium">
                    <span className="mt-0.5 w-6 h-6 rounded-full bg-violet-600 text-white flex items-center justify-center shrink-0"><Check size={13} /></span>
                    {a}
                  </li>
                ))}
              </ul>
            </div>
          </div>
        </div>
      </section>

      {/* Trust */}
      <section className="border-y border-slate-100 bg-slate-50/70">
        <div className="max-w-6xl mx-auto px-4 sm:px-6 py-12 grid md:grid-cols-[auto_1fr] gap-8 items-center">
          <div className="flex items-center gap-3 text-left">
            <span className={`w-12 h-12 rounded-2xl ${GRADIENT} text-white flex items-center justify-center`}><ShieldCheck size={22} /></span>
            <p className="text-xl font-extrabold max-w-[14rem] leading-tight">{t('Automação que protege sua conta', 'Automation that protects your account')}</p>
          </div>
          <div className="grid sm:grid-cols-2 lg:grid-cols-4 gap-4 text-sm text-slate-600 text-left">
            <p><b className="text-slate-900">{t('APIs oficiais.', 'Official APIs.')}</b> {t('Sem QR code nem conexões paralelas.', 'No QR codes or unofficial connections.')}</p>
            <p><b className="text-slate-900">{t('Regras da Meta.', "Meta's rules.")}</b> {t('Janela de 24h e opt-in aplicados no sistema.', '24h window and opt-in enforced in the product.')}</p>
            <p><b className="text-slate-900">{t('Dados protegidos.', 'Protected data.')}</b> {t('Tokens criptografados e isolados por empresa.', 'Tokens encrypted and isolated per business.')}</p>
            <p><b className="text-slate-900">{t('Controle total.', 'Full control.')}</b> {t('Desconecte e exclua seus dados quando quiser.', 'Disconnect and delete your data any time.')}</p>
          </div>
        </div>
      </section>

      {/* FAQ */}
      <section id="faq" className="max-w-3xl mx-auto px-4 sm:px-6 py-20">
        <h2 className="text-3xl sm:text-4xl font-extrabold tracking-tight text-center">{t('Perguntas frequentes', 'Frequently asked questions')}</h2>
        <div className="mt-10 space-y-3">
          {faqs.map((f) => (
            <details key={f.q} className="group rounded-2xl border border-slate-200 px-5 py-4 text-left open:border-violet-300 open:bg-violet-50/40">
              <summary className="flex items-center justify-between gap-4 cursor-pointer list-none font-bold text-slate-900">
                {f.q}
                <ChevronDown size={18} className="text-violet-500 shrink-0 transition-transform group-open:rotate-180" />
              </summary>
              <p className="mt-3 text-sm text-slate-600 leading-relaxed">{f.a}</p>
            </details>
          ))}
        </div>
      </section>

      {/* Final CTA */}
      <section className="px-4 sm:px-6 pb-20">
        <div className={`max-w-6xl mx-auto rounded-[2rem] px-6 py-14 sm:px-12 text-center text-white ${GRADIENT}`}>
          <h2 className="text-3xl sm:text-[2.6rem] font-extrabold tracking-tight leading-tight">
            {t('Seu próximo cliente já está comentando', 'Your next customer is already commenting')}
          </h2>
          <p className="mt-3 text-white/90 max-w-xl mx-auto">
            {t('Crie sua primeira automação hoje e responda cada lead na hora.', 'Build your first automation today and answer every lead instantly.')}
          </p>
          <button onClick={goSignup} className="mt-8 inline-flex items-center gap-2 px-7 py-3.5 rounded-full bg-white text-violet-700 font-extrabold hover:bg-violet-50">
            {t('Começar grátis', 'Start for free')} <ArrowRight size={18} />
          </button>
          <p className="mt-3 text-xs text-white/80">{t('7 dias grátis · sem cartão de crédito', '7-day free trial · no credit card')}</p>
        </div>
      </section>

      {/* Footer */}
      <footer className="bg-[#140b2e] text-violet-200/70">
        <div className="max-w-6xl mx-auto px-4 sm:px-6 py-14 grid sm:grid-cols-2 lg:grid-cols-4 gap-10 text-sm text-left">
          <div>
            <Logo dark />
            <p className="mt-4 leading-relaxed">{t('Automação de Direct, disparos no WhatsApp e gestão de tráfego.', 'DM automation, WhatsApp broadcasts and paid traffic management.')}</p>
            <div className="mt-4"><LanguageToggle compact /></div>
          </div>
          <div>
            <p className="font-bold text-white">{t('Produto', 'Product')}</p>
            <ul className="mt-3 space-y-2">
              <li><a href="#automacao" className="hover:text-white">{t('Automação', 'Automation')}</a></li>
              <li><a href="#disparos" className="hover:text-white">{t('Disparos', 'Broadcasts')}</a></li>
              <li><a href="#trafego" className="hover:text-white">{t('Tráfego', 'Traffic')}</a></li>
              <li><Link to="/pricing" className="hover:text-white">{t('Preços', 'Pricing')}</Link></li>
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
              <li><Link to="/login" className="hover:text-white">{t('Entrar', 'Sign in')}</Link></li>
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
