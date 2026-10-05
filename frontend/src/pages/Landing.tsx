import { useNavigate } from 'react-router-dom'
import {
  MessageSquare, Megaphone,
  Building2, Zap, Check, ArrowRight,
  ShieldCheck, Smartphone, CheckCircle2,
  TrendingUp, Lock, RefreshCw, ExternalLink,
} from 'lucide-react'
import { BRANDING } from '../config/branding'

export default function Landing() {
  const navigate = useNavigate()

  const metrics = [
    { label: 'Conversão Comercial', value: '+34%', desc: 'aumento médio em fechamentos via WhatsApp' },
    { label: 'Tempo de 1º Resposta', value: '< 30s', desc: 'triagem e distribuição imediata de leads' },
    { label: 'ROAS Médio Rastreado', value: '4.8x', desc: 'atribuição real de receita a cada anúncio Meta' },
    { label: 'Disponibilidade API', value: '99.9%', desc: 'infraestrutura oficial Meta Cloud sem quedas' },
  ]

  const pipeline = [
    {
      step: '01',
      title: 'Captação & Atribuição',
      desc: 'Cada clique no anúncio do Meta Ads ou interação no Instagram é capturado instantaneamente com identificação exata da campanha e criativo de origem.',
      icon: Megaphone,
    },
    {
      step: '02',
      title: 'Triagem & Atendimento Imediato',
      desc: 'O contato entra na fila oficial do WhatsApp com distribuição inteligente para sua equipe comercial ou triagem automática por assistente treinado.',
      icon: MessageSquare,
    },
    {
      step: '03',
      title: 'Nutrição & Fechamento',
      desc: 'Follow-ups automáticos resgatam quem não respondeu, enquanto o histórico unificado acompanha o lead até a conversão final.',
      icon: TrendingUp,
    },
  ]

  const capabilities = [
    {
      icon: Building2,
      badge: 'Para Agências & Gestores',
      title: 'Multi-Tenant com Contas-Filhas Isoladas',
      desc: 'Gerencie dezenas de clientes em um único painel. Cada empresa tem seu próprio ambiente isolado, com login para o cliente acompanhar resultados e permissões customizadas por operador.',
    },
    {
      icon: Smartphone,
      badge: 'Meta Cloud API Oficial',
      title: 'WhatsApp Business Seguro & Estável',
      desc: 'Sem riscos de banimento por conexões piratas de QR code. Conecte o número da empresa diretamente aos servidores oficiais da Meta com suporte a templates e envio em massa homologado.',
    },
    {
      icon: Zap,
      badge: 'Inteligência de Atendimento (RAG)',
      title: 'Base de Conhecimento Própria',
      desc: 'Suba o catálogo, tabela de preços e FAQs da empresa. O assistente qualifica dúvidas com dados reais do seu negócio antes de transferir para o especialista humano.',
    },
    {
      icon: RefreshCw,
      badge: 'Recuperação Ativa',
      title: 'Follow-ups Automáticos & Reengajamento',
      desc: 'Crie réguas programadas para quem parou de responder após o primeiro contato. Recupere até 40% das oportunidades perdidas no vácuo das mensagens.',
    },
  ]

  const comparisonRows = [
    { need: 'Criar anúncios no Meta Ads', meta: true, prospecta: true },
    { need: 'Triagem e distribuição de leads com fila comercial', meta: false, prospecta: true },
    { need: 'Histórico cruzado da mesma pessoa (Insta + WhatsApp)', meta: false, prospecta: true },
    { need: 'Cálculo do Custo por LEAD REAL fechado (não apenas clique)', meta: false, prospecta: true },
    { need: 'Régua de follow-up para contatos que não responderam', meta: false, prospecta: true },
    { need: 'Painel multi-cliente com troca em 1 clique para agências', meta: false, prospecta: true },
  ]

  return (
    <div className="min-h-screen bg-[#030712] text-[#f8fafc] font-sans antialiased selection:bg-sky-500/20 selection:text-sky-200">
      
      {/* Top Navbar */}
      <nav className="sticky top-0 z-50 backdrop-blur-md bg-[#030712]/90 border-b border-white/[0.08]">
        <div className="max-w-7xl mx-auto flex items-center justify-between px-6 py-4">
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

          {/* Links Desktop */}
          <div className="hidden md:flex items-center gap-8 text-sm text-[#94a3b8]">
            <a href="#como-funciona" className="hover:text-white transition-colors">Como Funciona</a>
            <a href="#recursos" className="hover:text-white transition-colors">Recursos</a>
            <a href="#comparativo" className="hover:text-white transition-colors">Comparativo</a>
            <a href="#agencias" className="hover:text-white transition-colors">Para Agências</a>
            <button onClick={() => navigate('/pricing')} className="hover:text-white transition-colors">Planos</button>
          </div>

          <div className="flex items-center gap-3">
            <button
              onClick={() => navigate('/login')}
              className="px-4 py-2 text-sm text-[#94a3b8] hover:text-white transition-colors"
            >
              Entrar
            </button>
            <button
              onClick={() => navigate('/login')}
              className="px-4 py-2 rounded-lg text-sm font-semibold text-white bg-gradient-to-r from-[#0284c7] via-[#0ea5e9] to-[#38bdf8] shadow-md shadow-[#0284c7]/25 hover:brightness-110 hover:-translate-y-0.5 transition-all"
            >
              Começar Agora
            </button>
          </div>
        </div>
      </nav>

      {/* Hero Section */}
      <section className="relative pt-20 pb-16 px-6 overflow-hidden border-b border-white/[0.06]">
        {/* Subtle grid pattern background */}
        <div className="hero-grid absolute inset-0 opacity-80 pointer-events-none" />

        <div className="relative max-w-5xl mx-auto text-center">
          {/* Institution badge */}
          <div className="inline-flex items-center gap-2 px-3.5 py-1.5 rounded-full bg-[#070e22] border border-[#38bdf8]/25 text-xs text-sky-300 mb-8 shadow-sm">
            <ShieldCheck size={14} className="text-sky-400" />
            <span>Plataforma Oficial de Prospecção & Conversão Omnichannel · <strong>Destrava Sistemas</strong></span>
          </div>

          {/* Main Title */}
          <h1 className="text-4xl sm:text-5xl md:text-6xl font-extrabold tracking-tight text-white leading-[1.1] mb-6">
            Escale suas vendas no WhatsApp, Instagram e Meta Ads <span className="bg-gradient-to-r from-sky-400 via-cyan-300 to-white bg-clip-text text-transparent">sem perder nenhum lead</span>
          </h1>

          {/* Subtitle */}
          <p className="text-base sm:text-lg md:text-xl text-[#94a3b8] max-w-3xl mx-auto mb-10 leading-relaxed font-normal">
            Centralize seus anúncios da Meta, triagem comercial no WhatsApp e automação de Direct em um único ambiente de alta performance. Desenvolvido para empresas com vendas ativas e agências de alta escala.
          </p>

          {/* CTAs */}
          <div className="flex flex-wrap items-center justify-center gap-4 mb-10">
            <button
              onClick={() => navigate('/login')}
              className="px-7 py-3.5 rounded-xl font-semibold text-white bg-gradient-to-r from-[#0284c7] via-[#0ea5e9] to-[#38bdf8] shadow-xl shadow-[#0284c7]/30 hover:brightness-110 hover:-translate-y-0.5 transition-all flex items-center gap-2 text-base"
            >
              Criar Conta Gratuita <ArrowRight size={18} />
            </button>
            <a
              href="#demonstracao"
              className="px-6 py-3.5 rounded-xl font-semibold border border-white/[0.12] bg-[#070e22]/60 text-[#f8fafc] hover:border-sky-400/50 hover:text-sky-300 transition-colors text-base"
            >
              Conhecer o Sistema
            </a>
          </div>

          {/* Trust badges */}
          <div className="flex flex-wrap items-center justify-center gap-6 text-xs text-[#64748b]">
            <div className="flex items-center gap-1.5">
              <CheckCircle2 size={14} className="text-sky-400" />
              <span>Sem necessidade de cartão de crédito</span>
            </div>
            <div className="flex items-center gap-1.5">
              <CheckCircle2 size={14} className="text-sky-400" />
              <span>Conexão direta Meta Cloud API</span>
            </div>
            <div className="flex items-center gap-1.5">
              <CheckCircle2 size={14} className="text-sky-400" />
              <span>Isolamento Multi-Tenant por Empresa</span>
            </div>
          </div>
        </div>

        {/* Real Product UI Mockup (Eliminates the "generic AI" look) */}
        <div id="demonstracao" className="relative max-w-6xl mx-auto mt-14 pt-4">
          <div className="rounded-2xl border border-[#38bdf8]/20 bg-[#070e22] shadow-2xl shadow-sky-950/60 overflow-hidden">
            {/* Window titlebar */}
            <div className="px-4 py-3 bg-[#030712] border-b border-white/[0.08] flex items-center justify-between text-xs text-[#64748b]">
              <div className="flex items-center gap-2">
                <span className="w-3 h-3 rounded-full bg-red-500/80 inline-block" />
                <span className="w-3 h-3 rounded-full bg-amber-500/80 inline-block" />
                <span className="w-3 h-3 rounded-full bg-emerald-500/80 inline-block" />
                <span className="ml-3 font-mono text-[11px] text-[#94a3b8] hidden sm:inline">
                  https://app.prospecta.destravasistemas.com.br
                </span>
              </div>
              <div className="flex items-center gap-3">
                <span className="inline-flex items-center gap-1.5 px-2 py-0.5 rounded bg-emerald-500/10 text-emerald-400 text-[11px] font-medium border border-emerald-500/20">
                  <span className="w-1.5 h-1.5 rounded-full bg-emerald-400 animate-pulse" />
                  Meta API: Operacional
                </span>
                <span className="hidden sm:inline text-[#94a3b8]">Workspace: <strong>Destrava Matriz</strong></span>
              </div>
            </div>

            {/* Dashboard Interface Preview */}
            <div className="grid grid-cols-1 lg:grid-cols-12 divide-y lg:divide-y-0 lg:divide-x divide-white/[0.06] bg-[#070e22]">
              
              {/* Left Column: Live Inbox Simulator */}
              <div className="lg:col-span-4 p-4 space-y-3">
                <div className="flex items-center justify-between pb-2 border-b border-white/[0.06]">
                  <div className="flex items-center gap-2">
                    <MessageSquare size={16} className="text-sky-400" />
                    <span className="text-sm font-semibold text-white">Fila de Atendimento</span>
                  </div>
                  <span className="text-xs bg-sky-500/15 text-sky-300 px-2 py-0.5 rounded font-mono font-medium">32 ativos</span>
                </div>

                {/* Conversation Cards */}
                <div className="space-y-2">
                  <div className="p-3 rounded-xl bg-sky-500/10 border border-sky-400/30 text-left cursor-default">
                    <div className="flex items-center justify-between text-xs mb-1">
                      <span className="font-semibold text-white">Lucas Mendes</span>
                      <span className="text-sky-300 text-[10px]">Agora mesmo</span>
                    </div>
                    <p className="text-xs text-[#cbd5e1] truncate mb-2">"Olá! Vi o anúncio de vocês no Instagram e quero saber..."</p>
                    <div className="flex items-center gap-2 text-[10px]">
                      <span className="px-1.5 py-0.5 rounded bg-sky-400/20 text-sky-200 font-medium">Anúncio: Reels Escala</span>
                      <span className="text-emerald-400 font-semibold">Lead Quente</span>
                    </div>
                  </div>

                  <div className="p-3 rounded-xl bg-white/[0.02] border border-white/[0.06] text-left opacity-80">
                    <div className="flex items-center justify-between text-xs mb-1">
                      <span className="font-medium text-white">Camila Rodrigues</span>
                      <span className="text-[#64748b] text-[10px]">4 min atrás</span>
                    </div>
                    <p className="text-xs text-[#94a3b8] truncate mb-1">"Qual o prazo para integração com meu CRM?"</p>
                    <span className="px-1.5 py-0.5 rounded bg-white/[0.05] text-[#94a3b8] text-[10px]">WhatsApp Direto</span>
                  </div>

                  <div className="p-3 rounded-xl bg-white/[0.02] border border-white/[0.06] text-left opacity-60">
                    <div className="flex items-center justify-between text-xs mb-1">
                      <span className="font-medium text-white">Rodrigo Silva</span>
                      <span className="text-[#64748b] text-[10px]">18 min atrás</span>
                    </div>
                    <p className="text-xs text-[#94a3b8] truncate mb-1">"Proposta enviada em PDF. Aguardando retorno."</p>
                    <span className="px-1.5 py-0.5 rounded bg-amber-500/10 text-amber-300 text-[10px]">Follow-up Automático D+2</span>
                  </div>
                </div>
              </div>

              {/* Center Column: Live Conversation / CRM Profile */}
              <div className="lg:col-span-5 p-5 flex flex-col justify-between text-left">
                <div>
                  <div className="flex items-center justify-between pb-3 border-b border-white/[0.06] mb-4">
                    <div>
                      <h4 className="text-sm font-bold text-white">Lucas Mendes</h4>
                      <p className="text-xs text-[#94a3b8]">+55 (11) 98765-4321 · São Paulo, SP</p>
                    </div>
                    <span className="text-xs px-2.5 py-1 rounded-full bg-emerald-500/15 border border-emerald-500/30 text-emerald-300 font-medium">
                      Oportunidade: R$ 4.500
                    </span>
                  </div>

                  {/* Chat bubbles */}
                  <div className="space-y-3 mb-4 text-xs">
                    <div className="bg-[#030712] border border-white/[0.08] p-3 rounded-xl rounded-tl-none max-w-[85%]">
                      <span className="text-[10px] text-sky-400 font-semibold block mb-0.5">Origem: Meta Ads (Instagram Feed)</span>
                      Olá! Vi o anúncio de vocês sobre automação de WhatsApp para agências. Gostaria de saber como funciona o plano multi-cliente.
                    </div>
                    <div className="bg-[#0284c7]/20 border border-[#38bdf8]/30 p-3 rounded-xl rounded-tr-none ml-auto max-w-[85%] text-sky-100">
                      <span className="text-[10px] text-sky-300 font-semibold block mb-0.5">Assistente Comercial (IA)</span>
                      Olá Lucas! Perfeito. No plano Agência você consegue gerenciar clientes ilimitados em ambientes isolados com login próprio. Deseja que eu agende uma demonstração com nosso consultor?
                    </div>
                  </div>
                </div>

                <div className="pt-3 border-t border-white/[0.06] flex items-center justify-between text-xs text-[#94a3b8]">
                  <span className="flex items-center gap-1.5">
                    <Lock size={12} className="text-sky-400" />
                    Criptografia Fernet em repouso
                  </span>
                  <span className="text-sky-400 font-medium cursor-pointer hover:underline">
                    Assumir atendimento humano →
                  </span>
                </div>
              </div>

              {/* Right Column: Real-Time Performance Analytics */}
              <div className="lg:col-span-3 p-4 space-y-3 bg-[#030712]/50 text-left">
                <div className="pb-2 border-b border-white/[0.06]">
                  <span className="text-xs font-bold uppercase tracking-wider text-[#94a3b8]">Métricas da Operação</span>
                </div>

                <div className="p-3 rounded-xl bg-[#070e22] border border-white/[0.06]">
                  <span className="text-[11px] text-[#94a3b8] block">Leads Capturados (Mês)</span>
                  <div className="flex items-baseline gap-2 mt-1">
                    <span className="text-xl font-bold text-white">1.842</span>
                    <span className="text-xs text-emerald-400 font-semibold">+22.4%</span>
                  </div>
                </div>

                <div className="p-3 rounded-xl bg-[#070e22] border border-white/[0.06]">
                  <span className="text-[11px] text-[#94a3b8] block">Custo Médio por Lead (CPA)</span>
                  <div className="flex items-baseline gap-2 mt-1">
                    <span className="text-xl font-bold text-white">R$ 3,18</span>
                    <span className="text-xs text-emerald-400 font-semibold">-14% vs meta</span>
                  </div>
                </div>

                <div className="p-3 rounded-xl bg-[#070e22] border border-white/[0.06]">
                  <span className="text-[11px] text-[#94a3b8] block">Taxa de Resposta 1º Contato</span>
                  <div className="flex items-baseline gap-2 mt-1">
                    <span className="text-xl font-bold text-white">96.8%</span>
                    <span className="text-xs text-sky-400 font-semibold">Instantâneo</span>
                  </div>
                </div>
              </div>

            </div>
          </div>
        </div>
      </section>

      {/* Metrics Banner */}
      <section className="py-12 px-6 border-b border-white/[0.06] bg-[#070e22]/40">
        <div className="max-w-6xl mx-auto grid grid-cols-2 md:grid-cols-4 gap-8 text-center">
          {metrics.map((m) => (
            <div key={m.label} className="space-y-1">
              <div className="text-3xl sm:text-4xl font-extrabold text-white tracking-tight">
                {m.value}
              </div>
              <div className="text-sm font-bold text-sky-300">{m.label}</div>
              <div className="text-xs text-[#94a3b8]">{m.desc}</div>
            </div>
          ))}
        </div>
      </section>

      {/* Workflow: Como Funciona */}
      <section id="como-funciona" className="py-20 px-6 max-w-6xl mx-auto border-b border-white/[0.06]">
        <div className="text-center max-w-3xl mx-auto mb-16">
          <span className="text-xs font-bold uppercase tracking-wider text-sky-400">Fluxo Operacional</span>
          <h2 className="text-3xl md:text-4xl font-bold text-white mt-2">
            Como o {BRANDING.name} transforma cliques em faturamento real
          </h2>
          <p className="text-sm sm:text-base text-[#94a3b8] mt-3">
            Acabe com o abismo entre o gestor de tráfego que entrega cliques e o time comercial que não atende a tempo.
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

      {/* Capabilities: Recursos Principais */}
      <section id="recursos" className="py-20 px-6 max-w-6xl mx-auto border-b border-white/[0.06]">
        <div className="text-center max-w-3xl mx-auto mb-16">
          <span className="text-xs font-bold uppercase tracking-wider text-sky-400">Recursos de Engenharia</span>
          <h2 className="text-3xl md:text-4xl font-bold text-white mt-2">
            Construído para operações comerciais que não podem falhar
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

      {/* Comparison: Meta Isolada vs Prospecta */}
      <section id="comparativo" className="py-20 px-6 max-w-4xl mx-auto border-b border-white/[0.06]">
        <div className="text-center mb-12">
          <span className="text-xs font-bold uppercase tracking-wider text-sky-400">Análise Comparativa</span>
          <h2 className="text-3xl md:text-4xl font-bold text-white mt-2">
            Por que usar o {BRANDING.name} e não apenas o gerenciador da Meta?
          </h2>
          <p className="text-sm sm:text-base text-[#94a3b8] mt-3">
            O Meta Ads Manager foi feito para cobrar por impressão. O {BRANDING.name} foi feito para gerar fechamentos comerciais.
          </p>
        </div>

        <div className="rounded-2xl border border-white/[0.08] bg-[#070e22] overflow-hidden shadow-xl">
          <div className="grid grid-cols-[1fr_auto_auto] text-sm">
            <div className="px-6 py-4 text-[#94a3b8] text-xs font-bold uppercase tracking-wider border-b border-white/[0.08]">
              Funcionalidade Operacional
            </div>
            <div className="px-6 py-4 text-[#64748b] text-xs font-bold uppercase tracking-wider border-b border-white/[0.08] text-center">
              Gerenciador Meta
            </div>
            <div className="px-6 py-4 text-sky-300 text-xs font-bold uppercase tracking-wider border-b border-white/[0.08] text-center bg-sky-500/10">
              {BRANDING.name}
            </div>

            {comparisonRows.map((row) => (
              <div key={row.need} className="contents">
                <div className="px-6 py-4 text-[#cbd5e1] border-b border-white/[0.04] text-left">
                  {row.need}
                </div>
                <div className="px-6 py-4 text-center border-b border-white/[0.04]">
                  {row.meta ? (
                    <Check size={16} className="inline text-[#64748b]" />
                  ) : (
                    <span className="text-[#475569] font-bold">—</span>
                  )}
                </div>
                <div className="px-6 py-4 text-center border-b border-white/[0.04] bg-sky-500/5">
                  <Check size={16} className="inline text-sky-400 font-bold" />
                </div>
              </div>
            ))}
          </div>
        </div>
      </section>

      {/* Agency Section */}
      <section id="agencias" className="py-20 px-6 max-w-6xl mx-auto border-b border-white/[0.06]">
        <div className="rounded-3xl border border-[#38bdf8]/20 bg-gradient-to-br from-[#070e22] via-[#070e22] to-[#0b152d] p-8 md:p-12 text-left relative overflow-hidden">
          <div className="max-w-2xl">
            <span className="text-xs font-bold uppercase tracking-wider text-sky-400 mb-3 block">
              Para Agências de Tráfego & Performance
            </span>
            <h2 className="text-3xl md:text-4xl font-bold text-white mb-4">
              Venda o software com a sua marca e entregue automação pronta para cada cliente
            </h2>
            <p className="text-sm sm:text-base text-[#94a3b8] leading-relaxed mb-6">
              Em vez de entregar apenas relatórios em PDF de cliques e impressões, entregue o ecossistema completo onde os leads do seu cliente são atendidos e convertidos em vendas reais.
            </p>
            <div className="flex flex-wrap gap-4">
              <button
                onClick={() => navigate('/login')}
                className="px-6 py-3 rounded-xl font-semibold text-white bg-gradient-to-r from-[#0284c7] via-[#0ea5e9] to-[#38bdf8] shadow-lg shadow-[#0284c7]/25 hover:brightness-110 transition-all text-sm"
              >
                Cadastrar Agência
              </button>
              <button
                onClick={() => navigate('/pricing')}
                className="px-6 py-3 rounded-xl font-semibold border border-white/[0.12] text-[#cbd5e1] hover:text-white hover:border-white/[0.2] transition-colors text-sm"
              >
                Ver Planos para Agências
              </button>
            </div>
          </div>
        </div>
      </section>

      {/* Final CTA */}
      <section className="py-24 px-6 text-center max-w-4xl mx-auto">
        <h2 className="text-3xl sm:text-4xl md:text-5xl font-extrabold text-white mb-4 tracking-tight">
          Pronto para profissionalizar sua prospecção?
        </h2>
        <p className="text-base text-[#94a3b8] max-w-xl mx-auto mb-8">
          Crie sua conta em 3 minutos, conecte sua conta da Meta e comece a captar e atender clientes com padrão institucional.
        </p>
        <button
          onClick={() => navigate('/login')}
          className="px-8 py-4 rounded-xl font-semibold text-white bg-gradient-to-r from-[#0284c7] via-[#0ea5e9] to-[#38bdf8] shadow-xl shadow-[#0284c7]/35 hover:brightness-110 hover:-translate-y-0.5 transition-all text-base inline-flex items-center gap-2"
        >
          Iniciar Teste Gratuito <ArrowRight size={18} />
        </button>
      </section>

      {/* Footer */}
      <footer className="border-t border-white/[0.08] bg-[#02050e] py-12 px-6 text-xs text-[#64748b]">
        <div className="max-w-6xl mx-auto flex flex-col md:flex-row items-center justify-between gap-6">
          <div className="flex flex-col sm:flex-row items-center gap-3">
            <span className="font-bold text-white text-sm">{BRANDING.name}</span>
            <span className="hidden sm:inline text-white/20">|</span>
            <span className="text-sky-400/90 font-medium">{BRANDING.authorCredit}</span>
          </div>

          <div className="flex items-center gap-6">
            <button onClick={() => navigate('/pricing')} className="hover:text-white transition-colors">Planos</button>
            <button onClick={() => navigate('/privacy')} className="hover:text-white transition-colors">Privacidade</button>
            <button onClick={() => navigate('/login')} className="hover:text-white transition-colors">Acesso ao Painel</button>
            <a href="https://destravasistemas.com.br" target="_blank" rel="noopener noreferrer" className="hover:text-sky-400 transition-colors flex items-center gap-1">
              Destrava Sistemas <ExternalLink size={12} />
            </a>
          </div>
        </div>
        <div className="max-w-6xl mx-auto mt-6 pt-6 border-t border-white/[0.04] text-center text-[#475569]">
          <p>© {new Date().getFullYear()} {BRANDING.name}. Uma plataforma desenvolvida e mantida por Destrava Sistemas. Todos os direitos reservados.</p>
        </div>
      </footer>

    </div>
  )
}
