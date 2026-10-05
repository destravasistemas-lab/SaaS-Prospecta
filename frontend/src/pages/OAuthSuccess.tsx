import { useEffect } from 'react'
import { useSearchParams } from 'react-router-dom'

export default function OAuthSuccess() {
  const [searchParams] = useSearchParams()
  const provider = searchParams.get('provider') || 'instagram'
  const username = searchParams.get('username') || ''

  useEffect(() => {
    if (window.opener) {
      window.opener.postMessage(
        { type: 'OAUTH_SUCCESS', provider, username },
        window.location.origin,
      )
    }
    if (provider === 'instagram') {
      // Instagram: mostra o perfil conectado como confirmação visual
      const igUrl = username
        ? `https://www.instagram.com/${username}/`
        : 'https://www.instagram.com/'
      window.location.href = igUrl
    } else {
      // Ads/WhatsApp: fecha o popup — a janela principal mostra o modal de sucesso
      window.close()
    }
  }, [])

  return (
    <div className="min-h-screen bg-[#0a0a0f] flex items-center justify-center">
      <div className="flex gap-1.5">
        {[0, 1, 2].map(i => (
          <div
            key={i}
            className="w-2 h-2 rounded-full bg-indigo-500 animate-bounce"
            style={{ animationDelay: `${i * 0.15}s` }}
          />
        ))}
      </div>
    </div>
  )
}
