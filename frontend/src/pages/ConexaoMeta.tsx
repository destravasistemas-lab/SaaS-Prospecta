import { useEffect, useRef, useState } from 'react'
import api from '../services/api'

type Provider = 'instagram' | 'whatsapp' | 'ads'

declare global {
  interface Window {
    FB?: any
    fbAsyncInit?: () => void
  }
}

function loadFacebookSdk(appId: string, graphVersion = 'v21.0'): Promise<void> {
  return new Promise((resolve) => {
    if (window.FB) {
      resolve()
      return
    }
    window.fbAsyncInit = () => {
      window.FB!.init({ appId, autoLogAppEvents: true, xfbml: false, version: graphVersion })
      resolve()
    }
    if (document.getElementById('facebook-jssdk')) return
    const script = document.createElement('script')
    script.id = 'facebook-jssdk'
    script.src = 'https://connect.facebook.net/en_US/sdk.js'
    script.async = true
    script.defer = true
    document.body.appendChild(script)
  })
}

interface Connection {
  id: string
  provider: Provider
  page_id: string | null
  ig_business_account_id: string | null
  waba_id: string | null
  phone_number: string | null
  ad_account_id: string | null
  status: 'active' | 'expired' | 'needs_reauth' | 'revoked'
  expires_at: string | null
  scopes: string[]
  created_at: string
}

/** Detalhe específico do provider mostrado no card quando conectado. */
function connectionDetail(conn: Connection): string | null {
  switch (conn.provider) {
    case 'whatsapp':
      return conn.phone_number
        ? `Número: ${conn.phone_number}${conn.waba_id ? ` · WABA ${conn.waba_id}` : ''}`
        : conn.waba_id ? `WABA: ${conn.waba_id}` : null
    case 'instagram':
      return conn.ig_business_account_id
        ? `Conta IG: ${conn.ig_business_account_id}${conn.page_id ? ` · Página ${conn.page_id}` : ''}`
        : conn.page_id ? `Página: ${conn.page_id}` : null
    case 'ads':
      return conn.ad_account_id ? `Ad Account: ${conn.ad_account_id}` : null
  }
}

const PROVIDERS: { key: Provider; label: string; icon: string; description: string }[] = [
  {
    key: 'instagram',
    label: 'Instagram',
    icon: '📸',
    description: 'DMs, comentários, publicação de posts e mídias.',
  },
  {
    key: 'whatsapp',
    label: 'WhatsApp Business',
    icon: '💬',
    description: 'Envio de mensagens e templates via WhatsApp Business.',
  },
  {
    key: 'ads',
    label: 'Meta Ads',
    icon: '📊',
    description: 'Gerenciamento e análise de campanhas de anúncios.',
  },
]

const STATUS_LABEL: Record<Connection['status'], string> = {
  active: 'Conectado',
  expired: 'Expirado',
  needs_reauth: 'Reautenticação necessária',
  revoked: 'Revogado',
}

const STATUS_COLOR: Record<Connection['status'], string> = {
  active: 'text-green-400',
  expired: 'text-yellow-400',
  needs_reauth: 'text-orange-400',
  revoked: 'text-red-400',
}

type ModalState = 'waiting' | 'success' | null

export default function ConexaoMeta() {
  const accountId = localStorage.getItem('tenant_id') ?? localStorage.getItem('account_id') ?? ''
  const [connections, setConnections] = useState<Connection[]>([])
  const [loading, setLoading] = useState(true)
  const [connecting, setConnecting] = useState<Provider | null>(null)
  const [disconnecting, setDisconnecting] = useState<string | null>(null)
  const [error, setError] = useState('')
  const [modal, setModal] = useState<{ state: ModalState; provider: Provider | null; username?: string }>({
    state: null,
    provider: null,
  })
  const [waError, setWaError] = useState('')

  const waCode = useRef<string | null>(null)
  const waPayload = useRef<{ waba_id?: string; phone_number_id?: string; business_id?: string } | null>(null)
  const waCompleting = useRef(false)

  useEffect(() => {
    if (accountId) loadConnections()
    else setLoading(false)
  }, [accountId])

  // Escuta as informações da sessão (session info v3) do Embedded Signup,
  // emitidas pela janela do Facebook via postMessage (formato WA_EMBEDDED_SIGNUP).
  useEffect(() => {
    function onFbMessage(event: MessageEvent) {
      if (event.origin !== 'https://www.facebook.com' && event.origin !== 'https://web.facebook.com') return
      if (typeof event.data !== 'string') return
      let data: any
      try {
        data = JSON.parse(event.data)
      } catch {
        return
      }
      if (data?.type !== 'WA_EMBEDDED_SIGNUP') return

      if (data.event === 'CANCEL') {
        // v3 informa em qual etapa o usuário abandonou o fluxo
        if (data.data?.current_step) {
          setWaError(`Cadastro cancelado na etapa "${data.data.current_step}". Tente novamente.`)
        }
        setConnecting(null)
        setModal({ state: null, provider: null })
      } else if (data.event === 'ERROR') {
        setWaError(data.data?.error_message || 'Erro no cadastro do WhatsApp.')
        setConnecting(null)
        setModal({ state: null, provider: null })
      } else if (data.event === 'FINISH_ONLY_WABA') {
        // Conta criada sem número de telefone — não dá para enviar mensagens
        setWaError(
          'A conta do WhatsApp Business foi criada, mas nenhum número de telefone foi adicionado. ' +
          'Refaça a conexão e adicione um número no fluxo.',
        )
        setConnecting(null)
        setModal({ state: null, provider: null })
      } else if (typeof data.event === 'string' && data.event.startsWith('FINISH')) {
        // FINISH ou FINISH_WHATSAPP_BUSINESS_APP_ONBOARDING: temos WABA + número
        waPayload.current = {
          waba_id: data.data?.waba_id,
          phone_number_id: data.data?.phone_number_id,
          business_id: data.data?.business_id,
        }
        tryCompleteEmbeddedSignup()
      }
    }
    window.addEventListener('message', onFbMessage)
    return () => window.removeEventListener('message', onFbMessage)
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [])

  async function tryCompleteEmbeddedSignup() {
    if (waCompleting.current) return
    if (!waCode.current || !waPayload.current?.waba_id || !waPayload.current?.phone_number_id) return
    waCompleting.current = true
    try {
      await api.post('/whatsapp/embedded-signup/complete', {
        code: waCode.current,
        waba_id: waPayload.current.waba_id,
        phone_number_id: waPayload.current.phone_number_id,
        business_id: waPayload.current.business_id,
      })
      setConnecting(null)
      setModal({ state: 'success', provider: 'whatsapp' })
      loadConnections()
    } catch (err: any) {
      setWaError(err.response?.data?.detail || 'Erro ao finalizar a conexão do WhatsApp.')
      setModal({ state: null, provider: null })
    } finally {
      waCode.current = null
      waPayload.current = null
      waCompleting.current = false
    }
  }

  interface EmbeddedSignupConfig {
    app_id: string
    config_id: string
    graph_api_version: string
    version: string
    session_info_version: string
    setup: Record<string, any>
  }

  async function handleConnectWhatsApp() {
    setError('')
    setWaError('')
    setConnecting('whatsapp')
    try {
      const { data } = await api.get<EmbeddedSignupConfig>('/whatsapp/embedded-signup/config')
      await loadFacebookSdk(data.app_id, data.graph_api_version)

      setModal({ state: 'waiting', provider: 'whatsapp' })
      window.FB.login(
        (response: any) => {
          if (response.authResponse?.code) {
            // Troca o code por token no backend (server-to-server, exige app secret)
            waCode.current = response.authResponse.code
            tryCompleteEmbeddedSignup()
          } else {
            setConnecting(null)
            setModal({ state: null, provider: null })
          }
        },
        {
          config_id: data.config_id,
          response_type: 'code',
          override_default_response_type: true,
          extras: {
            // Preenchimento automático com os dados do tenant (nome, e-mail)
            setup: data.setup ?? {},
            featureType: '',
            sessionInfoVersion: data.session_info_version || '3',
            version: data.version || 'v4',
          },
        },
      )
    } catch (err: any) {
      setWaError(err.response?.data?.detail || 'Embedded Signup não configurado.')
      setConnecting(null)
      setModal({ state: null, provider: null })
    }
  }

  useEffect(() => {
    // Recebe mensagem do popup OAuth quando conectar com sucesso
    const onMessage = (event: MessageEvent) => {
      if (event.origin !== window.location.origin) return
      if (event.data?.type === 'OAUTH_SUCCESS' && event.data?.provider === 'instagram') {
        setConnecting(null)
        setModal({ state: 'success', provider: 'instagram', username: event.data.username || '' })
        loadConnections()
      }
    }
    window.addEventListener('message', onMessage)
    return () => window.removeEventListener('message', onMessage)
  }, [])

  async function loadConnections() {
    try {
      const res = await api.get<Connection[]>('/auth/meta/connections')
      setConnections(res.data)
    } catch {
      setError('Erro ao carregar conexões.')
    } finally {
      setLoading(false)
    }
  }

  async function handleConnect(provider: Provider) {
    if (provider === 'whatsapp') {
      await handleConnectWhatsApp()
      return
    }

    const tid = localStorage.getItem('tenant_id')
    if (!tid) {
      setError('Conta não identificada. Faça login primeiro.')
      return
    }
    setError('')
    setConnecting(provider)
    setModal({ state: 'waiting', provider })

    try {
      const endpoint = provider === 'instagram' ? '/auth/instagram/start' : '/auth/meta/start'
      const params: Record<string, string> = provider === 'instagram'
        ? { account_id: tid }
        : { account_id: tid, provider }
      const res = await api.get<{ auth_url: string }>(endpoint, { params })

      if (!res.data.auth_url) {
        setError('Erro ao obter URL de autenticação.')
        setConnecting(null)
        setModal({ state: null, provider: null })
        return
      }

      const w = 520, h = 700
      const left = Math.round((window.screen.width - w) / 2)
      const top = Math.round((window.screen.height - h) / 2)
      const popup = window.open(
        res.data.auth_url,
        'oauth_popup',
        `width=${w},height=${h},left=${left},top=${top},toolbar=no,menubar=no,scrollbars=yes`,
      )

      if (!popup) {
        window.location.href = res.data.auth_url
        return
      }

      const onMessage = (event: MessageEvent) => {
        if (event.origin !== window.location.origin) return
        if (event.data?.type === 'OAUTH_SUCCESS') {
          cleanup()
          setConnecting(null)
          setModal({ state: 'success', provider, username: event.data.username || '' })
          loadConnections()
        }
      }
      const pollTimer = setInterval(() => {
        if (popup.closed) {
          cleanup()
          setConnecting(null)
          setModal(prev => prev.state === 'waiting' ? { state: null, provider: null } : prev)
        }
      }, 500)
      const cleanup = () => {
        clearInterval(pollTimer)
        window.removeEventListener('message', onMessage)
      }
      window.addEventListener('message', onMessage)
    } catch {
      setError('Erro de conexão com o servidor.')
      setConnecting(null)
      setModal({ state: null, provider: null })
    }
  }

  async function handleDisconnect(connection: Connection) {
    const tid = localStorage.getItem('tenant_id')
    if (!confirm(`Desconectar ${PROVIDERS.find(p => p.key === connection.provider)?.label}?`)) return
    setDisconnecting(connection.id)
    setError('')
    try {
      await api.delete(`/auth/meta/connections/${connection.id}`, {
        params: { account_id: tid },
      })
      setConnections(prev => prev.filter(c => c.id !== connection.id))
    } catch {
      setError('Erro ao desconectar. Tente novamente.')
    } finally {
      setDisconnecting(null)
    }
  }

  function getConnection(provider: Provider): Connection | undefined {
    return connections.find(c => c.provider === provider)
  }

  function closeModal() {
    setModal({ state: null, provider: null })
  }

  if (!accountId) {
    return (
      <div>
        <h2 className="text-2xl font-bold text-[#e2e2e8] mb-6">Conexão Meta</h2>
        <div className="bg-[#111118] rounded-xl border border-white/[0.06] p-8 max-w-lg text-center">
          <p className="text-[#555] text-sm">Complete o onboarding para conectar suas contas.</p>
        </div>
      </div>
    )
  }

  const token = localStorage.getItem('access_token')
  if (!token) {
    return (
      <div>
        <h2 className="text-2xl font-bold text-[#e2e2e8] mb-6">Conexão Meta</h2>
        <div className="bg-[#111118] rounded-xl border border-white/[0.06] p-8 max-w-lg text-center">
          <p className="text-[#555] text-sm">Faça login primeiro para conectar suas contas.</p>
        </div>
      </div>
    )
  }

  return (
    <div>
      <h2 className="text-2xl font-bold text-[#e2e2e8] mb-2">Conexão Meta</h2>
      <p className="text-[#555] text-sm mb-6">
        Conecte suas contas do Instagram, WhatsApp e Meta Ads para automatizar a gestão.
      </p>

      {error && (
        <div className="mb-4 bg-red-900/20 border border-red-500/20 text-red-400 text-sm rounded-lg px-4 py-3">
          {error}
        </div>
      )}
      {waError && (
        <div className="mb-4 bg-red-900/20 border border-red-500/20 text-red-400 text-sm rounded-lg px-4 py-3">
          {waError}
        </div>
      )}

      {loading ? (
        <div className="text-[#555] text-sm">Carregando conexões...</div>
      ) : (
        <div className="grid gap-4 max-w-2xl">
          {PROVIDERS.map(({ key, label, icon, description }) => {
            const conn = getConnection(key)
            const isConnected = conn?.status === 'active'
            const needsAction = conn && conn.status !== 'active'

            return (
              <div
                key={key}
                className="bg-[#111118] rounded-xl border border-white/[0.06] p-6 flex items-center gap-4"
              >
                <div className="w-12 h-12 rounded-full bg-indigo-500/10 flex items-center justify-center text-2xl flex-shrink-0">
                  {icon}
                </div>

                <div className="flex-1 min-w-0">
                  <div className="flex items-center gap-2">
                    <h3 className="text-[#e2e2e8] font-semibold text-sm">{label}</h3>
                    {conn && (
                      <span className={`text-xs font-medium ${STATUS_COLOR[conn.status]}`}>
                        • {STATUS_LABEL[conn.status]}
                      </span>
                    )}
                  </div>
                  <p className="text-[#555] text-xs mt-0.5">{description}</p>
                  {conn && isConnected && connectionDetail(conn) && (
                    <p className="text-emerald-400/80 text-xs mt-1 truncate">{connectionDetail(conn)}</p>
                  )}
                  {conn?.expires_at && (
                    <p className="text-[#444] text-xs mt-1">
                      Expira em: {new Date(conn.expires_at).toLocaleDateString('pt-BR')}
                    </p>
                  )}
                </div>

                <div className="flex gap-2 flex-shrink-0">
                  {isConnected ? (
                    <button
                      onClick={() => handleDisconnect(conn)}
                      disabled={disconnecting === conn.id}
                      className="px-3 py-1.5 bg-red-900/20 text-red-400 rounded-lg text-xs font-medium hover:bg-red-900/40 transition-colors disabled:opacity-50"
                    >
                      {disconnecting === conn.id ? 'Removendo...' : 'Desconectar'}
                    </button>
                  ) : (
                    <button
                      onClick={() => handleConnect(key)}
                      disabled={connecting === key}
                      className="px-3 py-1.5 bg-indigo-600 hover:bg-indigo-500 disabled:bg-indigo-600/50 text-white rounded-lg text-xs font-semibold transition-colors"
                    >
                      {connecting === key ? 'Aguardando...' : needsAction ? 'Reconectar' : 'Conectar'}
                    </button>
                  )}
                </div>
              </div>
            )
          })}
        </div>
      )}

      {/* Modal de conexão OAuth / Embedded Signup */}
      {modal.state !== null && modal.provider && (() => {
        const isWa = modal.provider === 'whatsapp'
        const gradient = isWa
          ? 'from-[#25d366] to-[#128c7e]'
          : 'from-[#f09433] via-[#dc2743] to-[#bc1888]'
        const gradientBar = isWa
          ? 'from-[#25d366] to-[#128c7e]'
          : 'from-[#f09433] via-[#e6683c] via-[#dc2743] via-[#cc2366] to-[#bc1888]'
        const icon = PROVIDERS.find(p => p.key === modal.provider)?.icon ?? '🔗'
        const label = PROVIDERS.find(p => p.key === modal.provider)?.label ?? modal.provider

        return (
          <div className="fixed inset-0 z-50 flex items-center justify-center bg-black/60 backdrop-blur-sm">
            <div className="bg-[#111118] border border-white/[0.08] rounded-2xl w-full max-w-sm mx-4 overflow-hidden shadow-2xl">
              <div className={`h-1.5 bg-gradient-to-r ${gradientBar}`} />

              <div className="p-8 flex flex-col items-center text-center">
                {modal.state === 'waiting' ? (
                  <>
                    <div className={`w-16 h-16 rounded-2xl bg-gradient-to-br ${gradient} flex items-center justify-center mb-5 shadow-lg`}>
                      <span className="text-3xl">{icon}</span>
                    </div>
                    <h3 className="text-[#e2e2e8] font-semibold text-base mb-2">Conectando {label}</h3>
                    <p className="text-[#555] text-sm mb-6">
                      {isWa
                        ? 'Complete o cadastro na janela do Facebook que abriu. Aguardando...'
                        : `Autorize o acesso na janela do ${label} que abriu. Aguardando...`}
                    </p>
                    <div className="flex gap-1.5 mb-6">
                      {[0, 1, 2].map(i => (
                        <div
                          key={i}
                          className="w-2 h-2 rounded-full bg-indigo-500 animate-bounce"
                          style={{ animationDelay: `${i * 0.15}s` }}
                        />
                      ))}
                    </div>
                    <button
                      onClick={closeModal}
                      className="text-[#444] text-xs hover:text-[#666] transition-colors"
                    >
                      Cancelar
                    </button>
                  </>
                ) : (
                  <>
                    <div className={`w-16 h-16 rounded-2xl bg-gradient-to-br ${gradient} flex items-center justify-center mb-5 shadow-lg`}>
                      <span className="text-3xl">{icon}</span>
                    </div>
                    <div className="w-8 h-8 rounded-full bg-green-500 flex items-center justify-center -mt-10 ml-10 mb-3 border-2 border-[#111118]">
                      <svg className="w-4 h-4 text-white" fill="none" viewBox="0 0 24 24" stroke="currentColor" strokeWidth={3}>
                        <path strokeLinecap="round" strokeLinejoin="round" d="M5 13l4 4L19 7" />
                      </svg>
                    </div>
                    <h3 className="text-[#e2e2e8] font-semibold text-base mb-1">{label} conectado!</h3>
                    {modal.username && (
                      <p className="text-indigo-400 text-sm font-medium mb-1">@{modal.username}</p>
                    )}
                    <p className="text-[#555] text-xs mb-6">
                      {isWa
                        ? 'Seu número está pronto para enviar e receber mensagens.'
                        : 'Sua conta está pronta para DMs, comentários e publicações.'}
                    </p>
                    <button
                      onClick={closeModal}
                      className="w-full py-2.5 bg-indigo-600 hover:bg-indigo-500 text-white rounded-xl text-sm font-semibold transition-colors"
                    >
                      Fechar
                    </button>
                  </>
                )}
              </div>
            </div>
          </div>
        )
      })()}
    </div>
  )
}
