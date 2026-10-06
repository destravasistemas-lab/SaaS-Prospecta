import { useEffect } from 'react'
import { useSearchParams } from 'react-router-dom'
import { useI18n } from '../i18n'

export default function OAuthSuccess() {
  const { t } = useI18n()
  const [searchParams] = useSearchParams()
  const provider = searchParams.get('provider') || 'instagram'
  const username = searchParams.get('username') || ''
  const error = searchParams.get('error') || ''

  useEffect(() => {
    if (window.opener) {
      window.opener.postMessage(
        error
          ? { type: 'OAUTH_ERROR', provider, error }
          : { type: 'OAUTH_SUCCESS', provider, username },
        window.location.origin,
      )
      // A janela principal mostra o resultado — o popup fecha sozinho
      window.close()
    }
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [])

  return (
    <div className="min-h-screen bg-[#030712] flex flex-col items-center justify-center gap-4 px-4 text-center">
      {error ? (
        <>
          <p className="text-white font-semibold">{t('A conexão não foi concluída', 'The connection was not completed')}</p>
          <p className="text-sm text-[#94a3b8] max-w-sm">{error}</p>
        </>
      ) : (
        <>
          <p className="text-white font-semibold">{t('Conta conectada!', 'Account connected!')}</p>
          <p className="text-sm text-[#94a3b8]">{t('Você já pode fechar esta janela.', 'You can close this window now.')}</p>
        </>
      )}
      <a href="/app/conexao" className="text-sm text-sky-400 underline">
        {t('Voltar para Conexões Meta', 'Back to Meta Connections')}
      </a>
    </div>
  )
}
