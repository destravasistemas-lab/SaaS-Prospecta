import { useNavigate } from 'react-router-dom'
import {
  Camera, MessageSquare, Megaphone, Send, Clock, Calendar,
  Building2, Zap, Users, Check, ArrowRight, Sparkles, BarChart3,
} from 'lucide-react'

const NEON = 'from-[#ff4fd8] via-[#a855f7] to-[#00d4ff]'

function Grad({ children }: { children: React.ReactNode }) {
  return <span className={`bg-gradient-to-r ${NEON} bg-clip-text text-transparent`}>{children}</span>
}

export default function Landing() {
  const navigate = useNavigate()

  const integrations = [
    {
      icon: Camera, accent: '#ff4fd8', name: 'Instagram',
      desc: 'Publique e agende posts, Reels e Stories. Responda o Direct pelo painel e crie funis de comentário → DM automáticos.',
      points: ['Publicar & agendar', 'Direct unificado', 'Automação comentário→DM', 'Métricas e insights'],
    },
    {
      icon: MessageSquare, accent: '#25D366', name: 'WhatsApp Business',
      desc: 'Atendimento com filas (bot, espera, humano), envio de mídia, templates aprovados e disparo em massa — tudo na janela oficial da Meta.',
      points: ['Inbox com 3 filas', 'Templates + custo', 'Disparo em massa', 'Bot por palavra-chave'],
    },
    {
      icon: Megaphone, accent: '#00d4ff', name: 'Meta Ads',
      desc: 'Crie campanhas, conjuntos e anúncios (imagem, vídeo, carrossel ou impulsionar um post). Veja resultados, CPA, ROAS e leads por anúncio.',
      points: ['Campanhas completas', 'Segmentação + interesses', 'Resultados, CPA e ROAS', 'Atribuição de leads'],
    },
  ]

  const features = [
    { icon: Zap, title: 'IA treinada no SEU negócio (RAG)', text: 'Suba seus PDFs (catálogo, FAQ, políticas) e a IA responde no WhatsApp com as informações reais da sua empresa — inclusive áudios, que ela transcreve. Se ficar indisponível, a conversa cai na fila humana na hora.' },
    { icon: Send, title: 'Disparo & Follow-ups', text: 'Importe leads por CSV, dispare templates para listas segmentadas e recupere quem não respondeu com follow-ups automáticos (3 a 14 dias).' },
    { icon: Calendar, title: 'Cronograma de conteúdo', text: 'Agende posts do Instagram com data e hora e acompanhe o que está publicado, agendado ou falhou — num calendário só.' },
    { icon: BarChart3, title: 'Leads unificados', text: 'A mesma pessoa no Instagram e no WhatsApp vira um lead só. Histórico dos dois canais junto, atribuído ao anúncio de origem.' },
  ]

  const metaVsUs = [
    { need: 'Postar, responder DM, rodar anúncio', meta: true, us: true },
    { need: 'IA que responde com o conhecimento do SEU negócio', meta: false, us: true },
    { need: 'Mesma pessoa do Insta + WhatsApp num lead só', meta: false, us: true },
    { need: 'Custo por LEAD real de cada anúncio (não por clique)', meta: false, us: true },
    { need: 'Disparo em massa + follow-up de quem não respondeu', meta: false, us: true },
    { need: 'Vários clientes num painel só, com automações prontas', meta: false, us: true },
  ]

  const agencyPerks = [
    'Contas-filhas: gerencie cada empresa-cliente num tenant isolado',
    'Troque de cliente pelo seletor, sem relogar',
    'Acesso compartilhado com o dono da empresa (login próprio)',
    'Controle de acesso por membro da equipe',
    'Ofereça as automações prontas para cada cliente',
    'Conecte Instagram, WhatsApp e Ads dentro da conta do cliente',
  ]

  return (
    <div className="min-h-screen bg-[#05060a] text-[#f4f2fb] antialiased selection:bg-[#a855f7]/30">
      {/* ambient glow */}
      <div className="pointer-events-none fixed inset-0 overflow-hidden">
        <div className="absolute -top-40 left-1/2 -translate-x-1/2 w-[900px] h-[500px] rounded-full bg-[#a855f7]/12 blur-[130px]" />
        <div className="absolute top-20 right-0 w-[500px] h-[400px] rounded-full bg-[#00d4ff]/8 blur-[120px]" />
      </div>

      {/* nav */}
      <nav className="sticky top-0 z-40 backdrop-blur-md bg-[#05060a]/80 border-b border-white/[0.06]">
        <div className="max-w-6xl mx-auto flex items-center justify-between px-6 py-4">
          <button onClick={() => navigate('/')} className="flex items-center gap-2.5">
            <span className={`w-8 h-8 rounded-lg bg-gradient-to-br ${NEON} grid place-items-center text-white font-black shadow-lg shadow-[#a855f7]/40`}>A</span>
            <span className="font-semibold tracking-tight">ad<Grad>Studio</Grad>AI</span>
          </button>
          <div className="flex items-center gap-2">
            <button onClick={() => navigate('/login')} className="px-4 py-2 text-sm text-[#8b8fa6] hover:text-white transition-colors">
              Entrar
            </button>
            <button onClick={() => navigate('/login')}
              className={`px-4 py-2 rounded-lg text-sm font-semibold text-white bg-gradient-to-r ${NEON} shadow-lg shadow-[#a855f7]/30 hover:-translate-y-0.5 transition-transform`}>
              Criar conta
            </button>
          </div>
        </div>
      </nav>

      {/* hero */}
      <section className="relative overflow-hidden">
        {/* fundo aurora animado */}
        <div className="pointer-events-none absolute inset-0 overflow-hidden" aria-hidden="true">
          <div className="aurora-blob aurora-a absolute -top-32 left-[6%] w-[520px] h-[420px] bg-[#ff4fd8]/20" />
          <div className="aurora-blob aurora-b absolute -top-24 right-[4%] w-[560px] h-[460px] bg-[#00d4ff]/16" />
          <div className="aurora-blob aurora-c absolute top-8 left-1/2 -translate-x-1/2 w-[640px] h-[440px] bg-[#a855f7]/22" />
          <div className="hero-grid absolute inset-0" />
          <div className="absolute inset-x-0 bottom-0 h-40 bg-gradient-to-b from-transparent to-[#05060a]" />
        </div>
        <div className="relative max-w-4xl mx-auto text-center px-6 pt-24 pb-20">
        <div className="inline-flex items-center gap-2 px-3 py-1.5 rounded-full bg-white/[0.04] border border-white/[0.08] text-xs text-[#8b8fa6] mb-8">
          <Sparkles size={13} className="text-[#00d4ff]" />
          Instagram · WhatsApp · Meta Ads em um só painel
        </div>
        <h1 className="text-4xl md:text-6xl font-extrabold leading-[1.05] tracking-tight text-balance mb-6">
          Todo o seu marketing digital <Grad>num sistema só</Grad>
        </h1>
        <p className="text-lg text-[#8b8fa6] max-w-2xl mx-auto mb-10">
          Conecte suas redes, atenda e dispare mensagens, rode anúncios e deixe a IA qualificar seus leads —
          para autônomos e para agências que gerenciam vários clientes.
        </p>
        <div className="flex flex-wrap items-center justify-center gap-3">
          <button onClick={() => navigate('/login')}
            className={`group px-6 py-3 rounded-xl font-semibold text-white bg-gradient-to-r ${NEON} shadow-xl shadow-[#a855f7]/30 hover:-translate-y-0.5 transition-transform flex items-center gap-2`}>
            Criar conta grátis
            <ArrowRight size={17} className="group-hover:translate-x-0.5 transition-transform" />
          </button>
          <button onClick={() => navigate('/login')}
            className="px-6 py-3 rounded-xl font-semibold border border-white/[0.12] text-[#f4f2fb] hover:border-[#a855f7]/60 hover:text-[#c9a7ff] transition-colors">
            Já tenho conta
          </button>
        </div>
        </div>
      </section>

      {/* integrações */}
      <section className="relative max-w-6xl mx-auto px-6 py-16">
        <div className="text-center mb-12">
          <p className="text-xs font-bold uppercase tracking-[0.2em] text-[#00d4ff] mb-3">Integrações</p>
          <h2 className="text-3xl md:text-4xl font-bold tracking-tight text-balance">Cada canal, com tudo o que ele precisa</h2>
        </div>
        <div className="grid md:grid-cols-3 gap-5">
          {integrations.map((it) => {
            const Icon = it.icon
            return (
              <div key={it.name}
                className="rounded-2xl bg-[#11131a] border border-white/[0.07] p-6 hover:border-white/[0.14] hover:-translate-y-1 transition-all">
                <div className="w-11 h-11 rounded-xl grid place-items-center mb-4"
                  style={{ background: `${it.accent}1f`, border: `1px solid ${it.accent}47` }}>
                  <Icon size={20} style={{ color: it.accent }} />
                </div>
                <h3 className="text-lg font-bold mb-2">{it.name}</h3>
                <p className="text-sm text-[#8b8fa6] leading-relaxed mb-4">{it.desc}</p>
                <ul className="space-y-2">
                  {it.points.map((p) => (
                    <li key={p} className="flex items-center gap-2 text-sm text-[#c9c9d6]">
                      <Check size={14} style={{ color: it.accent }} className="shrink-0" /> {p}
                    </li>
                  ))}
                </ul>
              </div>
            )
          })}
        </div>
      </section>

      {/* features */}
      <section className="relative max-w-6xl mx-auto px-6 py-16">
        <div className="grid md:grid-cols-2 gap-5">
          {features.map((f) => {
            const Icon = f.icon
            return (
              <div key={f.title} className="rounded-2xl bg-gradient-to-br from-white/[0.04] to-transparent border border-white/[0.07] p-6 flex gap-4">
                <span className={`w-11 h-11 shrink-0 rounded-xl bg-gradient-to-br ${NEON} grid place-items-center text-white shadow-lg shadow-[#a855f7]/30`}>
                  <Icon size={19} />
                </span>
                <div>
                  <h3 className="font-bold mb-1.5">{f.title}</h3>
                  <p className="text-sm text-[#8b8fa6] leading-relaxed">{f.text}</p>
                </div>
              </div>
            )
          })}
        </div>
      </section>

      {/* por que não só a Meta grátis? */}
      <section className="relative max-w-4xl mx-auto px-6 py-16">
        <div className="text-center mb-10">
          <p className="text-xs font-bold uppercase tracking-[0.2em] text-[#00d4ff] mb-3">A pergunta certa</p>
          <h2 className="text-3xl md:text-4xl font-bold tracking-tight text-balance">
            "Por que não usar só as ferramentas <Grad>grátis da Meta</Grad>?"
          </h2>
          <p className="text-[#8b8fa6] mt-4 max-w-2xl mx-auto">
            Publicar e anunciar, a Meta já faz. O que ela não faz é a <b className="text-[#c9c9d6]">operação</b> que
            transforma seguidor em cliente — é essa camada que entregamos.
          </p>
        </div>
        <div className="rounded-2xl border border-white/[0.08] bg-[#11131a] overflow-hidden">
          <div className="grid grid-cols-[1fr_auto_auto] text-sm">
            <div className="px-5 py-3 text-[#555] text-xs font-bold uppercase tracking-wider border-b border-white/[0.06]">O que você precisa</div>
            <div className="px-5 py-3 text-[#555] text-xs font-bold uppercase tracking-wider border-b border-white/[0.06] text-center">Meta grátis</div>
            <div className="px-5 py-3 text-xs font-bold uppercase tracking-wider border-b border-white/[0.06] text-center"><Grad>adStudioAI</Grad></div>
            {metaVsUs.map((row) => (
              <div key={row.need} className="contents">
                <div className="px-5 py-3.5 text-[#c9c9d6] border-b border-white/[0.04]">{row.need}</div>
                <div className="px-5 py-3.5 text-center border-b border-white/[0.04]">
                  {row.meta ? <Check size={16} className="inline text-[#5c5f70]" /> : <span className="text-[#444]">—</span>}
                </div>
                <div className="px-5 py-3.5 text-center border-b border-white/[0.04]">
                  {row.us && <Check size={16} className="inline text-[#00d4ff]" />}
                </div>
              </div>
            ))}
          </div>
        </div>
      </section>

      {/* agência */}
      <section className="relative max-w-6xl mx-auto px-6 py-16">
        <div className="rounded-3xl border border-white/[0.08] bg-[#0b0c12] p-8 md:p-12 overflow-hidden relative">
          <div className="pointer-events-none absolute -top-24 -right-16 w-72 h-72 rounded-full bg-[#a855f7]/15 blur-[90px]" />
          <div className="relative grid md:grid-cols-2 gap-10 items-center">
            <div>
              <p className="text-xs font-bold uppercase tracking-[0.2em] text-[#ff4fd8] mb-3 flex items-center gap-2">
                <Building2 size={14} /> Para agências
              </p>
              <h2 className="text-3xl md:text-4xl font-bold tracking-tight text-balance mb-4">
                Gerencie <Grad>vários clientes</Grad> lado a lado com o dono
              </h2>
              <p className="text-[#8b8fa6] leading-relaxed mb-6">
                Cada empresa-cliente vira uma conta-filha isolada. Você opera tudo pela agência e o dono
                acompanha com o login dele — e você ainda entrega as automações prontas para cada um.
              </p>
              <div className="flex gap-3">
                <button onClick={() => navigate('/login')}
                  className={`px-5 py-2.5 rounded-xl font-semibold text-white bg-gradient-to-r ${NEON} shadow-lg shadow-[#a855f7]/30 hover:-translate-y-0.5 transition-transform`}>
                  Começar como agência
                </button>
              </div>
            </div>
            <ul className="grid gap-3">
              {agencyPerks.map((p) => (
                <li key={p} className="flex items-start gap-3 text-sm text-[#c9c9d6]">
                  <span className="w-5 h-5 shrink-0 rounded-full bg-[#a855f7]/15 border border-[#a855f7]/40 grid place-items-center mt-0.5">
                    <Check size={12} className="text-[#c9a7ff]" />
                  </span>
                  {p}
                </li>
              ))}
            </ul>
          </div>
        </div>
      </section>

      {/* CTA final */}
      <section className="relative max-w-3xl mx-auto text-center px-6 py-20">
        <div className="inline-flex items-center gap-2 text-[#8b8fa6] text-sm mb-5">
          <Users size={15} className="text-[#00d4ff]" /> Autônomos e agências
        </div>
        <h2 className="text-3xl md:text-5xl font-extrabold tracking-tight text-balance mb-5">
          Pronto pra centralizar <Grad>tudo</Grad>?
        </h2>
        <p className="text-[#8b8fa6] mb-9 max-w-xl mx-auto">
          Crie sua conta em minutos, conecte suas redes e comece a atender, publicar e anunciar do mesmo lugar.
        </p>
        <div className="flex flex-wrap items-center justify-center gap-3">
          <button onClick={() => navigate('/login')}
            className={`px-7 py-3.5 rounded-xl font-semibold text-white bg-gradient-to-r ${NEON} shadow-xl shadow-[#a855f7]/40 hover:-translate-y-0.5 transition-transform flex items-center gap-2`}>
            Criar conta grátis <ArrowRight size={18} />
          </button>
          <button onClick={() => navigate('/login')}
            className="px-7 py-3.5 rounded-xl font-semibold border border-white/[0.12] hover:border-[#a855f7]/60 hover:text-[#c9a7ff] transition-colors">
            Entrar
          </button>
        </div>
      </section>

      {/* footer */}
      <footer className="border-t border-white/[0.06] mt-8">
        <div className="max-w-6xl mx-auto px-6 py-8 flex flex-col sm:flex-row items-center justify-between gap-4 text-sm text-[#5c5f70]">
          <span className="font-semibold text-[#8b8fa6]">ad<Grad>Studio</Grad>AI</span>
          <div className="flex items-center gap-5">
            <button onClick={() => navigate('/pricing')} className="hover:text-[#c9c9d6] transition-colors flex items-center gap-1.5">
              <Clock size={13} /> Planos
            </button>
            <button onClick={() => navigate('/privacy')} className="hover:text-[#c9c9d6] transition-colors">Privacidade</button>
            <button onClick={() => navigate('/login')} className="hover:text-[#c9c9d6] transition-colors">Entrar</button>
          </div>
        </div>
      </footer>
    </div>
  )
}
