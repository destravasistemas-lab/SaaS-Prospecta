import { useNavigate } from 'react-router-dom'
import {
  MessageSquare, Megaphone,
  Building2, Zap, Check, ArrowRight,
  ShieldCheck, Smartphone, CheckCircle2,
  TrendingUp, Lock, RefreshCw, ExternalLink,
} from 'lucide-react'
import { BRANDING } from '../config/branding'
import { useI18n, LanguageToggle } from '../i18n'

export default function Landing() {
  const navigate = useNavigate()
  const { t } = useI18n()

  const highlights = [
    { value: t('APIs oficiais', 'Official APIs'), label: 'WhatsApp · Instagram · Ads', desc: t('WhatsApp Cloud API, Instagram API e Marketing API da Meta', "Meta's WhatsApp Cloud API, Instagram API and Marketing API") },
    { value: '24h', label: t('Janela respeitada', 'Window enforced'), desc: t('mensagens livres só dentro da janela de atendimento', 'free-form messages only inside the service window') },
    { value: 'Opt-in', label: t('Consentimento', 'Consent'), desc: t('templates só para contatos que aceitaram receber', 'templates only to contacts who agreed to receive them') },
    { value: 'LGPD', label: t('Privacidade', 'Privacy'), desc: t('tokens criptografados e exclusão de dados automática', 'encrypted tokens and automatic data deletion') },
  ]

  const pipeline = [
    {
      step: '01',
      title: t('Captação & Atribuição', 'Capture & Attribution'),
      desc: t(
        'Leads de anúncios Click-to-WhatsApp, formulários de Lead Ads, comentários e Direct do Instagram entram com a campanha e o anúncio de origem identificados.',
        'Leads from Click-to-WhatsApp ads, Lead Ads forms, Instagram comments and Direct come in with their source campaign and ad identified.',
      ),
      icon: Megaphone,
    },
    {
      step: '02',
      title: t('Atendimento em uma caixa única', 'Service in one inbox'),
      desc: t(
        'WhatsApp e Instagram Direct na mesma tela, com filas para a equipe, respostas automáticas por palavra-chave e assistente de IA que transfere para um humano.',
        'WhatsApp and Instagram Direct in one screen, with team queues, keyword auto-replies and an AI assistant that hands off to a human.',
      ),
      icon: MessageSquare,
    },
    {
      step: '03',
      title: t('Acompanhamento & Fechamento', 'Follow-up & Closing'),
      desc: t(
        'Follow-ups com templates aprovados para contatos com opt-in, e histórico unificado do lead até a venda.',
        'Follow-ups with approved templates for opted-in contacts, and a unified lead history all the way to the sale.',
      ),
      icon: TrendingUp,
    },
  ]

  const capabilities = [
    {
      icon: Building2,
      badge: t('Para Agências & Gestores', 'For Agencies & Managers'),
      title: t('Multi-empresa com ambientes isolados', 'Multi-business with isolated workspaces'),
      desc: t(
        'Gerencie vários clientes em um painel. Cada empresa tem seu ambiente isolado, login próprio e permissões por operador.',
        'Manage many clients from one panel. Each business has its own isolated workspace, its own login and per-operator permissions.',
      ),
    },
    {
      icon: Smartphone,
      badge: 'WhatsApp Cloud API',
      title: t('WhatsApp Business pela API oficial', 'WhatsApp Business via the official API'),
      desc: t(
        'Conexão pelo Cadastro Incorporado (Embedded Signup) da Meta — sem QR code ou conexões não oficiais. Templates aprovados pela Meta e disparos apenas para contatos com opt-in.',
        "Connected through Meta's Embedded Signup — no QR codes or unofficial connections. Meta-approved templates and broadcasts only to opted-in contacts.",
      ),
    },
    {
      icon: Zap,
      badge: t('Assistente de IA', 'AI Assistant'),
      title: t('Base de conhecimento da sua empresa', "Your business's knowledge base"),
      desc: t(
        'Envie catálogo, preços e FAQs. O assistente responde só sobre o seu negócio, se identifica como automatizado e transfere para um humano quando pedido.',
        'Upload your catalog, prices and FAQs. The assistant only answers about your business, identifies itself as automated and hands off to a human on request.',
      ),
    },
    {
      icon: RefreshCw,
      badge: t('Instagram', 'Instagram'),
      title: t('Publicação, comentários e Direct', 'Publishing, comments and Direct'),
      desc: t(
        'Agende posts, responda comentários e envie uma resposta privada no Direct para quem comentar uma palavra-chave.',
        'Schedule posts, reply to comments and send a private Direct reply to people who comment a keyword.',
      ),
    },
  ]

  const comparisonRows = [
    { need: t('Criar e acompanhar campanhas no Meta Ads', 'Create and track Meta Ads campaigns'), meta: true },
    { need: t('Caixa de entrada única WhatsApp + Instagram com filas de equipe', 'Single WhatsApp + Instagram inbox with team queues'), meta: false },
    { need: t('Histórico da mesma pessoa entre Instagram e WhatsApp', 'Same-person history across Instagram and WhatsApp'), meta: false },
    { need: t('Leads e conversas atribuídos a cada anúncio', 'Leads and conversations attributed to each ad'), meta: false },
    { need: t('Follow-ups com templates para contatos com opt-in', 'Template follow-ups for opted-in contacts'), meta: false },
    { need: t('Painel multi-cliente para agências', 'Multi-client panel for agencies'), meta: false },
  ]

  return (
    <div className="min-h-screen bg-[#030712] text-[#f8fafc] font-sans antialiased selection:bg-sky-500/20 selection:text-sky-200">

      {/* Top Navbar */}
      <nav className="sticky top-0 z-50 backdrop-blur-md bg-[#030712]/90 border-b border-white/[0.08]">
        <div className="max-w-7xl mx-auto flex items-center justify-between px-4 sm:px-6 py-4 gap-3">
          <button onClick={() => navigate('/')} className="flex items-center gap-3 group text-left">
            <div className="w-8 h-8 rounded-lg bg-gradient-to-br from-[#0284c7] via-[#0ea5e9] to-[#38bdf8] flex items-center justify-center font-bold text-white shadow-md shadow-[#0ea5e9]/25">
              P
            </div>
            <div className="flex flex-col">
              <span className="font-bold text-[15px] tracking-tight text-white leading-none">
                {BRANDING.name}
              </span>
              <span className="text-[10px] text-sky-400 font-medium tracking-wide">
                by {BRANDING.company}
              </span>
            </div>
          </button>

          <div className="hidden md:flex items-center gap-8 text-sm text-[#94a3b8]">
            <a href="#como-funciona" className="hover:text-white transition-colors">{t('Como Funciona', 'How It Works')}</a>
            <a href="#recursos" className="hover:text-white transition-colors">{t('Recursos', 'Features')}</a>
            <a href="#comparativo" className="hover:text-white transition-colors">{t('Comparativo', 'Comparison')}</a>
            <a href="#agencias" className="hover:text-white transition-colors">{t('Para Agências', 'For Agencies')}</a>
            <button onClick={() => navigate('/pricing')} className="hover:text-white transition-colors">{t('Planos', 'Pricing')}</button>
          </div>

          <div className="flex items-center gap-2 sm:gap-3">
            <LanguageToggle compact className="hidden sm:inline-flex" />
            <button
              onClick={() => navigate('/login')}
              className="px-3 sm:px-4 py-2 text-sm text-[#94a3b8] hover:text-white transition-colors"
            >
              {t('Entrar', 'Sign in')}
            </button>
            <button
              onClick={() => navigate('/login')}
              className="px-3 sm:px-4 py-2 rounded-lg text-sm font-semibold text-white bg-gradient-to-r from-[#0284c7] via-[#0ea5e9] to-[#38bdf8] shadow-md shadow-[#0284c7]/25 hover:brightness-110 hover:-translate-y-0.5 transition-all"
            >
              {t('Começar Agora', 'Get Started')}
            </button>
          </div>
        </div>
      </nav>

      {/* Hero Section */}
      <section className="relative pt-20 pb-16 px-4 sm:px-6 overflow-hidden border-b border-white/[0.06]">
        <div className="hero-grid absolute inset-0 opacity-80 pointer-events-none" />

        <div className="relative max-w-5xl mx-auto text-center">
          <div className="inline-flex items-center gap-2 px-3.5 py-1.5 rounded-full bg-[#070e22] border border-[#38bdf8]/25 text-xs text-sky-300 mb-8 shadow-sm">
            <ShieldCheck size={14} className="text-sky-400" />
            <span>{t('Construído sobre as APIs oficiais da Meta', "Built on Meta's official APIs")} · <strong>Destrava Sistemas</strong></span>
          </div>

          <h1 className="text-4xl sm:text-5xl md:text-6xl font-extrabold tracking-tight text-white leading-[1.1] mb-6">
            {t('Atenda e venda pelo WhatsApp, Instagram e Meta Ads', 'Serve and sell on WhatsApp, Instagram and Meta Ads')}{' '}
            <span className="bg-gradient-to-r from-sky-400 via-cyan-300 to-white bg-clip-text text-transparent">
              {t('sem perder nenhum lead', 'without losing a single lead')}
            </span>
          </h1>

          <p className="text-base sm:text-lg md:text-xl text-[#94a3b8] max-w-3xl mx-auto mb-10 leading-relaxed font-normal">
            {t(
              'Centralize anúncios da Meta, atendimento no WhatsApp e Direct do Instagram em um único painel. Feito para empresas com vendas ativas e agências.',
              'Bring Meta ads, WhatsApp customer service and Instagram Direct into a single panel. Built for businesses with active sales and agencies.',
            )}
          </p>

          <div className="flex flex-wrap items-center justify-center gap-4 mb-10">
            <button
              onClick={() => navigate('/login')}
              className="px-7 py-3.5 rounded-xl font-semibold text-white bg-gradient-to-r from-[#0284c7] via-[#0ea5e9] to-[#38bdf8] shadow-xl shadow-[#0284c7]/30 hover:brightness-110 hover:-translate-y-0.5 transition-all flex items-center gap-2 text-base"
            >
              {t('Criar Conta Gratuita', 'Create Free Account')} <ArrowRight size={18} />
            </button>
            <a
              href="#demonstracao"
              className="px-6 py-3.5 rounded-xl font-semibold border border-white/[0.12] bg-[#070e22]/60 text-[#f8fafc] hover:border-sky-400/50 hover:text-sky-300 transition-colors text-base"
            >
              {t('Conhecer o Sistema', 'See the Product')}
            </a>
          </div>

          <div className="flex flex-wrap items-center justify-center gap-6 text-xs text-[#64748b]">
            <div className="flex items-center gap-1.5">
              <CheckCircle2 size={14} className="text-sky-400" />
              <span>{t('Sem necessidade de cartão de crédito', 'No credit card required')}</span>
            </div>
            <div className="flex items-center gap-1.5">
              <CheckCircle2 size={14} className="text-sky-400" />
              <span>{t('WhatsApp Cloud API via Embedded Signup', 'WhatsApp Cloud API via Embedded Signup')}</span>
            </div>
            <div className="flex items-center gap-1.5">
              <CheckCircle2 size={14} className="text-sky-400" />
              <span>{t('Dados isolados por empresa', 'Data isolated per business')}</span>
            </div>
          </div>
        </div>

        {/* Product preview */}
        <div id="demonstracao" className="relative max-w-6xl mx-auto mt-14 pt-4">
          <div className="rounded-2xl border border-[#38bdf8]/20 bg-[#070e22] shadow-2xl shadow-sky-950/60 overflow-hidden">
            <div className="px-4 py-3 bg-[#030712] border-b border-white/[0.08] flex items-center justify-between text-xs text-[#64748b]">
              <div className="flex items-center gap-2">
                <span className="w-3 h-3 rounded-full bg-red-500/80 inline-block" />
                <span className="w-3 h-3 rounded-full bg-amber-500/80 inline-block" />
                <span className="w-3 h-3 rounded-full bg-emerald-500/80 inline-block" />
                <span className="ml-3 font-mono text-[11px] text-[#94a3b8] hidden sm:inline">
                  app.prospecta.destravasistemas.com.br
                </span>
              </div>
              <span className="text-[11px] text-[#64748b]">{t('Ilustração do produto', 'Product illustration')}</span>
            </div>

            <div className="grid grid-cols-1 lg:grid-cols-12 divide-y lg:divide-y-0 lg:divide-x divide-white/[0.06] bg-[#070e22]">
              <div className="lg:col-span-4 p-4 space-y-3">
                <div className="flex items-center justify-between pb-2 border-b border-white/[0.06]">
                  <div className="flex items-center gap-2">
                    <MessageSquare size={16} className="text-sky-400" />
                    <span className="text-sm font-semibold text-white">{t('Fila de Atendimento', 'Service Queue')}</span>
                  </div>
                </div>

                <div className="space-y-2">
                  <div className="p-3 rounded-xl bg-sky-500/10 border border-sky-400/30 text-left cursor-default">
                    <div className="flex items-center justify-between text-xs mb-1">
                      <span className="font-semibold text-white">Lucas Mendes</span>
                      <span className="text-sky-300 text-[10px]">{t('Agora mesmo', 'Just now')}</span>
                    </div>
                    <p className="text-xs text-[#cbd5e1] truncate mb-2">{t('"Olá! Vi o anúncio de vocês no Instagram e quero saber..."', '"Hi! I saw your ad on Instagram and I\'d like to know..."')}</p>
                    <div className="flex items-center gap-2 text-[10px]">
                      <span className="px-1.5 py-0.5 rounded bg-sky-400/20 text-sky-200 font-medium">{t('Anúncio: Reels', 'Ad: Reels')}</span>
                      <span className="text-emerald-400 font-semibold">{t('Lead Quente', 'Hot Lead')}</span>
                    </div>
                  </div>

                  <div className="p-3 rounded-xl bg-white/[0.02] border border-white/[0.06] text-left opacity-80">
                    <div className="flex items-center justify-between text-xs mb-1">
                      <span className="font-medium text-white">Camila Rodrigues</span>
                      <span className="text-[#64748b] text-[10px]">{t('4 min atrás', '4 min ago')}</span>
                    </div>
                    <p className="text-xs text-[#94a3b8] truncate mb-1">{t('"Qual o prazo de entrega?"', '"What is the delivery time?"')}</p>
                    <span className="px-1.5 py-0.5 rounded bg-white/[0.05] text-[#94a3b8] text-[10px]">WhatsApp</span>
                  </div>

                  <div className="p-3 rounded-xl bg-white/[0.02] border border-white/[0.06] text-left opacity-60">
                    <div className="flex items-center justify-between text-xs mb-1">
                      <span className="font-medium text-white">Rodrigo Silva</span>
                      <span className="text-[#64748b] text-[10px]">{t('18 min atrás', '18 min ago')}</span>
                    </div>
                    <p className="text-xs text-[#94a3b8] truncate mb-1">{t('"Recebi a proposta, vou analisar."', '"Got the proposal, I\'ll take a look."')}</p>
                    <span className="px-1.5 py-0.5 rounded bg-amber-500/10 text-amber-300 text-[10px]">Instagram Direct</span>
                  </div>
                </div>
              </div>

              <div className="lg:col-span-5 p-5 flex flex-col justify-between text-left">
                <div>
                  <div className="flex items-center justify-between pb-3 border-b border-white/[0.06] mb-4">
                    <div>
                      <h4 className="text-sm font-bold text-white">Lucas Mendes</h4>
                      <p className="text-xs text-[#94a3b8]">+55 (11) 9xxxx-xxxx</p>
                    </div>
                  </div>

                  <div className="space-y-3 mb-4 text-xs">
                    <div className="bg-[#030712] border border-white/[0.08] p-3 rounded-xl rounded-tl-none max-w-[85%]">
                      <span className="text-[10px] text-sky-400 font-semibold block mb-0.5">{t('Origem: anúncio Click-to-WhatsApp', 'Source: Click-to-WhatsApp ad')}</span>
                      {t(
                        'Olá! Vi o anúncio de vocês. Gostaria de saber como funciona o plano para agências.',
                        'Hi! I saw your ad. I would like to know how the agency plan works.',
                      )}
                    </div>
                    <div className="bg-[#0284c7]/20 border border-[#38bdf8]/30 p-3 rounded-xl rounded-tr-none ml-auto max-w-[85%] text-sky-100">
                      <span className="text-[10px] text-sky-300 font-semibold block mb-0.5">{t('Assistente virtual (automatizado)', 'Virtual assistant (automated)')}</span>
                      {t(
                        'Olá Lucas! No plano Agência você gerencia vários clientes em ambientes isolados. Quer que eu chame um consultor para te ajudar?',
                        'Hi Lucas! With the Agency plan you manage several clients in isolated workspaces. Would you like me to bring in a consultant to help you?',
                      )}
                    </div>
                  </div>
                </div>

                <div className="pt-3 border-t border-white/[0.06] flex items-center justify-between text-xs text-[#94a3b8]">
                  <span className="flex items-center gap-1.5">
                    <Lock size={12} className="text-sky-400" />
                    {t('Tokens criptografados em repouso', 'Tokens encrypted at rest')}
                  </span>
                  <span className="text-sky-400 font-medium">
                    {t('Assumir atendimento →', 'Take over conversation →')}
                  </span>
                </div>
              </div>

              <div className="lg:col-span-3 p-4 space-y-3 bg-[#030712]/50 text-left">
                <div className="pb-2 border-b border-white/[0.06]">
                  <span className="text-xs font-bold uppercase tracking-wider text-[#94a3b8]">{t('Métricas (exemplo)', 'Metrics (example)')}</span>
                </div>
                <div className="p-3 rounded-xl bg-[#070e22] border border-white/[0.06]">
                  <span className="text-[11px] text-[#94a3b8] block">{t('Leads no mês', 'Leads this month')}</span>
                  <span className="text-xl font-bold text-white">1,842</span>
                </div>
                <div className="p-3 rounded-xl bg-[#070e22] border border-white/[0.06]">
                  <span className="text-[11px] text-[#94a3b8] block">{t('Custo por lead', 'Cost per lead')}</span>
                  <span className="text-xl font-bold text-white">{t('R$ 3,18', '$0.64')}</span>
                </div>
                <div className="p-3 rounded-xl bg-[#070e22] border border-white/[0.06]">
                  <span className="text-[11px] text-[#94a3b8] block">{t('Conversas abertas', 'Open conversations')}</span>
                  <span className="text-xl font-bold text-white">32</span>
                </div>
              </div>
            </div>
          </div>
        </div>
      </section>

      {/* Highlights */}
      <section className="py-12 px-4 sm:px-6 border-b border-white/[0.06] bg-[#070e22]/40">
        <div className="max-w-6xl mx-auto grid grid-cols-2 md:grid-cols-4 gap-8 text-center">
          {highlights.map((m) => (
            <div key={m.label} className="space-y-1">
              <div className="text-2xl sm:text-3xl font-extrabold text-white tracking-tight">{m.value}</div>
              <div className="text-sm font-bold text-sky-300">{m.label}</div>
              <div className="text-xs text-[#94a3b8]">{m.desc}</div>
            </div>
          ))}
        </div>
      </section>

      {/* How it works */}
      <section id="como-funciona" className="py-20 px-4 sm:px-6 max-w-6xl mx-auto border-b border-white/[0.06]">
        <div className="text-center max-w-3xl mx-auto mb-16">
          <span className="text-xs font-bold uppercase tracking-wider text-sky-400">{t('Fluxo Operacional', 'Workflow')}</span>
          <h2 className="text-3xl md:text-4xl font-bold text-white mt-2">
            {t(`Como o ${BRANDING.name} transforma cliques em vendas`, `How ${BRANDING.name} turns clicks into sales`)}
          </h2>
          <p className="text-sm sm:text-base text-[#94a3b8] mt-3">
            {t(
              'Una quem gera os leads e quem atende, no mesmo lugar.',
              'Bring the people who generate leads and the people who answer them into the same place.',
            )}
          </p>
        </div>

        <div className="grid md:grid-cols-3 gap-8">
          {pipeline.map((p) => {
            const Icon = p.icon
            return (
              <div
                key={p.step}
                className="relative rounded-2xl bg-[#070e22] border border-white/[0.08] p-8 hover:border-sky-400/40 transition-colors flex flex-col justify-between"
              >
                <div>
                  <div className="flex items-center justify-between mb-6">
                    <span className="text-2xl font-black text-sky-400/40 font-mono">{p.step}</span>
                    <div className="w-10 h-10 rounded-xl bg-sky-500/10 border border-sky-400/25 flex items-center justify-center text-sky-300">
                      <Icon size={20} />
                    </div>
                  </div>
                  <h3 className="text-xl font-bold text-white mb-3">{p.title}</h3>
                  <p className="text-sm text-[#94a3b8] leading-relaxed">{p.desc}</p>
                </div>
              </div>
            )
          })}
        </div>
      </section>

      {/* Features */}
      <section id="recursos" className="py-20 px-4 sm:px-6 max-w-6xl mx-auto border-b border-white/[0.06]">
        <div className="text-center max-w-3xl mx-auto mb-16">
          <span className="text-xs font-bold uppercase tracking-wider text-sky-400">{t('Recursos', 'Features')}</span>
          <h2 className="text-3xl md:text-4xl font-bold text-white mt-2">
            {t('Feito para operações comerciais que não podem parar', "Built for sales operations that can't stop")}
          </h2>
        </div>

        <div className="grid md:grid-cols-2 gap-6">
          {capabilities.map((c) => {
            const Icon = c.icon
            return (
              <div
                key={c.title}
                className="rounded-2xl bg-[#070e22] border border-white/[0.08] p-8 hover:border-sky-400/30 transition-all text-left"
              >
                <div className="flex items-center justify-between mb-4">
                  <div className="w-10 h-10 rounded-xl bg-sky-500/10 border border-sky-400/20 flex items-center justify-center text-sky-300">
                    <Icon size={20} />
                  </div>
                  <span className="text-[11px] font-semibold text-sky-300 bg-sky-500/10 border border-sky-400/20 px-2.5 py-1 rounded-full">
                    {c.badge}
                  </span>
                </div>
                <h3 className="text-lg font-bold text-white mb-2">{c.title}</h3>
                <p className="text-sm text-[#94a3b8] leading-relaxed">{c.desc}</p>
              </div>
            )
          })}
        </div>
      </section>

      {/* Comparison */}
      <section id="comparativo" className="py-20 px-4 sm:px-6 max-w-4xl mx-auto border-b border-white/[0.06]">
        <div className="text-center mb-12">
          <span className="text-xs font-bold uppercase tracking-wider text-sky-400">{t('Comparativo', 'Comparison')}</span>
          <h2 className="text-3xl md:text-4xl font-bold text-white mt-2">
            {t(`O que o ${BRANDING.name} adiciona às ferramentas da Meta`, `What ${BRANDING.name} adds on top of Meta's tools`)}
          </h2>
          <p className="text-sm sm:text-base text-[#94a3b8] mt-3">
            {t(
              'Usamos as APIs da Meta e acrescentamos a camada de atendimento e vendas.',
              "We use Meta's APIs and add the customer service and sales layer.",
            )}
          </p>
        </div>

        <div className="rounded-2xl border border-white/[0.08] bg-[#070e22] overflow-hidden shadow-xl">
          <div className="grid grid-cols-[1fr_auto_auto] text-sm">
            <div className="px-4 sm:px-6 py-4 text-[#94a3b8] text-xs font-bold uppercase tracking-wider border-b border-white/[0.08]">
              {t('Funcionalidade', 'Capability')}
            </div>
            <div className="px-4 sm:px-6 py-4 text-[#64748b] text-xs font-bold uppercase tracking-wider border-b border-white/[0.08] text-center">
              {t('Ferramentas Meta', 'Meta tools')}
            </div>
            <div className="px-4 sm:px-6 py-4 text-sky-300 text-xs font-bold uppercase tracking-wider border-b border-white/[0.08] text-center bg-sky-500/10">
              {BRANDING.name}
            </div>

            {comparisonRows.map((row) => (
              <div key={row.need} className="contents">
                <div className="px-4 sm:px-6 py-4 text-[#cbd5e1] border-b border-white/[0.04] text-left">
                  {row.need}
                </div>
                <div className="px-4 sm:px-6 py-4 text-center border-b border-white/[0.04]">
                  {row.meta ? (
                    <Check size={16} className="inline text-[#64748b]" />
                  ) : (
                    <span className="text-[#475569] font-bold">—</span>
                  )}
                </div>
                <div className="px-4 sm:px-6 py-4 text-center border-b border-white/[0.04] bg-sky-500/5">
                  <Check size={16} className="inline text-sky-400 font-bold" />
                </div>
              </div>
            ))}
          </div>
        </div>
      </section>

      {/* Agency Section */}
      <section id="agencias" className="py-20 px-4 sm:px-6 max-w-6xl mx-auto border-b border-white/[0.06]">
        <div className="rounded-3xl border border-[#38bdf8]/20 bg-gradient-to-br from-[#070e22] via-[#070e22] to-[#0b152d] p-8 md:p-12 text-left relative overflow-hidden">
          <div className="max-w-2xl">
            <span className="text-xs font-bold uppercase tracking-wider text-sky-400 mb-3 block">
              {t('Para Agências de Tráfego & Performance', 'For Performance & Media Agencies')}
            </span>
            <h2 className="text-3xl md:text-4xl font-bold text-white mb-4">
              {t('Entregue atendimento e automação prontos para cada cliente', 'Deliver ready-made service and automation to every client')}
            </h2>
            <p className="text-sm sm:text-base text-[#94a3b8] leading-relaxed mb-6">
              {t(
                'Além de relatórios de cliques e impressões, entregue o ambiente onde os leads do seu cliente são atendidos e viram vendas.',
                "Beyond click and impression reports, deliver the workspace where your client's leads are served and turned into sales.",
              )}
            </p>
            <div className="flex flex-wrap gap-4">
              <button
                onClick={() => navigate('/login')}
                className="px-6 py-3 rounded-xl font-semibold text-white bg-gradient-to-r from-[#0284c7] via-[#0ea5e9] to-[#38bdf8] shadow-lg shadow-[#0284c7]/25 hover:brightness-110 transition-all text-sm"
              >
                {t('Cadastrar Agência', 'Sign Up as an Agency')}
              </button>
              <button
                onClick={() => navigate('/pricing')}
                className="px-6 py-3 rounded-xl font-semibold border border-white/[0.12] text-[#cbd5e1] hover:text-white hover:border-white/[0.2] transition-colors text-sm"
              >
                {t('Ver Planos para Agências', 'See Agency Plans')}
              </button>
            </div>
          </div>
        </div>
      </section>

      {/* Final CTA */}
      <section className="py-24 px-4 sm:px-6 text-center max-w-4xl mx-auto">
        <h2 className="text-3xl sm:text-4xl md:text-5xl font-extrabold text-white mb-4 tracking-tight">
          {t('Pronto para profissionalizar seu atendimento?', 'Ready to professionalize your customer service?')}
        </h2>
        <p className="text-base text-[#94a3b8] max-w-xl mx-auto mb-8">
          {t(
            'Crie sua conta, conecte suas contas da Meta e comece a atender clientes em minutos.',
            'Create your account, connect your Meta accounts and start serving customers in minutes.',
          )}
        </p>
        <button
          onClick={() => navigate('/login')}
          className="px-8 py-4 rounded-xl font-semibold text-white bg-gradient-to-r from-[#0284c7] via-[#0ea5e9] to-[#38bdf8] shadow-xl shadow-[#0284c7]/35 hover:brightness-110 hover:-translate-y-0.5 transition-all text-base inline-flex items-center gap-2"
        >
          {t('Iniciar Teste Gratuito', 'Start Free Trial')} <ArrowRight size={18} />
        </button>
      </section>

      {/* Footer */}
      <footer className="border-t border-white/[0.08] bg-[#02050e] py-12 px-4 sm:px-6 text-xs text-[#64748b]">
        <div className="max-w-6xl mx-auto flex flex-col md:flex-row items-center justify-between gap-6">
          <div className="flex flex-col sm:flex-row items-center gap-3">
            <span className="font-bold text-white text-sm">{BRANDING.name}</span>
            <span className="hidden sm:inline text-white/20">|</span>
            <span className="text-sky-400/90 font-medium">{t(BRANDING.authorCredit, 'A Destrava Sistemas solution')}</span>
          </div>

          <div className="flex flex-wrap items-center justify-center gap-x-6 gap-y-2">
            <button onClick={() => navigate('/pricing')} className="hover:text-white transition-colors">{t('Planos', 'Pricing')}</button>
            <button onClick={() => navigate('/privacy')} className="hover:text-white transition-colors">{t('Privacidade', 'Privacy')}</button>
            <button onClick={() => navigate('/terms')} className="hover:text-white transition-colors">{t('Termos', 'Terms')}</button>
            <button onClick={() => navigate('/data-deletion')} className="hover:text-white transition-colors">{t('Exclusão de Dados', 'Data Deletion')}</button>
            <button onClick={() => navigate('/login')} className="hover:text-white transition-colors">{t('Acesso ao Painel', 'Sign In')}</button>
            <a href={BRANDING.companyUrl} target="_blank" rel="noopener noreferrer" className="hover:text-sky-400 transition-colors flex items-center gap-1">
              Destrava Sistemas <ExternalLink size={12} />
            </a>
            <LanguageToggle compact className="sm:hidden" />
          </div>
        </div>
        <div className="max-w-6xl mx-auto mt-6 pt-6 border-t border-white/[0.04] text-center text-[#475569] space-y-2">
          <p>
            © {new Date().getFullYear()} {BRANDING.name}.{' '}
            {t(
              'Uma plataforma desenvolvida e mantida por Destrava Sistemas. Todos os direitos reservados.',
              'A platform developed and maintained by Destrava Sistemas. All rights reserved.',
            )}
          </p>
          <p>
            {t(
              'Meta, Facebook, Instagram e WhatsApp são marcas da Meta Platforms, Inc. Este produto não é afiliado nem endossado pela Meta.',
              'Meta, Facebook, Instagram and WhatsApp are trademarks of Meta Platforms, Inc. This product is not affiliated with or endorsed by Meta.',
            )}
          </p>
        </div>
      </footer>

    </div>
  )
}
