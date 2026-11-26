import { useEffect, useState } from 'react'
import { Link, useNavigate } from 'react-router-dom'
import { Download, Monitor, CheckCircle2, LogIn } from 'lucide-react'
import { BRANDING } from '../config/branding'
import { useI18n, LanguageToggle } from '../i18n'
import { canPromptInstall, detectPlatform, isInstalledApp, onInstallChange, promptInstall } from '../services/pwa'
import BrandMark from '../components/BrandMark'

/** Link para baixar o app: /instalar. Instala o Prospecta como app (ícone na área de trabalho) que abre no login. */
export default function Instalar() {
  const { t } = useI18n()
  const navigate = useNavigate()
  const [ready, setReady] = useState(canPromptInstall())
  const [installed, setInstalled] = useState(false)
  const platform = detectPlatform()
  const phone = platform === 'ios' || platform === 'android'

  useEffect(() => {
    if (isInstalledApp()) navigate('/login?source=app', { replace: true })
    return onInstallChange(() => setReady(canPromptInstall()))
  }, [navigate])

  async function install() {
    if (await promptInstall()) setInstalled(true)
  }

  const steps: Record<typeof platform, string[]> = {
    desktop: [
      t('Abra este link no Google Chrome ou no Microsoft Edge.', 'Open this link in Google Chrome or Microsoft Edge.'),
      t('Clique no ícone de instalar no fim da barra de endereço (um monitor com uma seta).', 'Click the install icon at the end of the address bar (a monitor with an arrow).'),
      t('Ou: menu ⋮ → "Transmitir, salvar e compartilhar" → "Instalar página como app" (no Edge: menu … → Aplicativos → "Instalar este site como aplicativo").', 'Or: ⋮ menu → "Cast, save and share" → "Install page as app" (in Edge: … menu → Apps → "Install this site as an app").'),
    ],
    'mac-safari': [
      t('No Safari, abra o menu Arquivo → "Adicionar ao Dock".', 'In Safari, open the File menu → "Add to Dock".'),
    ],
    ios: [
      t('No Safari, toque em Compartilhar (quadrado com seta para cima).', 'In Safari, tap Share (square with an up arrow).'),
      t('Escolha "Adicionar à Tela de Início" e confirme.', 'Choose "Add to Home Screen" and confirm.'),
    ],
    android: [
      t('No Chrome, toque no menu ⋮ → "Instalar app" (ou "Adicionar à tela inicial").', 'In Chrome, tap the ⋮ menu → "Install app" (or "Add to Home screen").'),
    ],
  }

  return (
    <div className="min-h-screen bg-[#0b0718] text-white flex flex-col items-center justify-center px-4 py-16 relative">
      <nav className="absolute top-0 left-0 right-0 flex items-center justify-between px-4 sm:px-7 py-[18px]">
        <a href="/" className="flex items-center gap-2 no-underline">
          <BrandMark className="w-6 h-6 rounded-md" />
          <span className="text-[13px] font-semibold tracking-tight">{BRANDING.name}</span>
        </a>
        <LanguageToggle />
      </nav>

      <div className="w-full max-w-md bg-white/[0.03] border border-white/[0.08] rounded-2xl p-6 sm:p-8">
        <BrandMark className="w-16 h-16 mx-auto mb-5 rounded-2xl shadow-lg shadow-violet-500/30" />
        <h1 className="text-xl font-semibold text-center tracking-tight">
          {phone
            ? t(`Instale o ${BRANDING.name} no seu celular`, `Install ${BRANDING.name} on your phone`)
            : t(`Instale o ${BRANDING.name} no seu computador`, `Install ${BRANDING.name} on your computer`)}
        </h1>
        <p className="text-sm text-violet-200/70 text-center mt-2">
          {phone
            ? t('Ícone na tela de início, avisos de mensagens e de leads interessados, e abre direto na tela de login. Atualiza sozinho.', 'Home screen icon, alerts for messages and interested leads, and it opens straight on the login screen. Updates itself.')
            : t('Ícone na área de trabalho, janela própria e abre direto na tela de login. Atualiza sozinho.', 'Desktop icon, its own window, and it opens straight on the login screen. Updates itself.')}
        </p>

        {installed ? (
          <div className="mt-6 flex items-start gap-3 bg-emerald-500/10 border border-emerald-400/20 rounded-xl p-4 text-sm text-emerald-200">
            <CheckCircle2 size={18} className="shrink-0 mt-0.5" />
            <span>{t(`Pronto! Abra pelo ícone "${BRANDING.name}" na área de trabalho ou no menu Iniciar.`, `Done! Open it from the "${BRANDING.name}" icon on your desktop or Start menu.`)}</span>
          </div>
        ) : ready ? (
          <button
            onClick={install}
            className="mt-6 w-full py-3 bg-gradient-to-r from-violet-600 via-fuchsia-500 to-orange-400 text-white text-sm font-semibold rounded-xl flex items-center justify-center gap-2 hover:brightness-110"
          >
            <Download size={16} /> {t('Instalar app', 'Install app')}
          </button>
        ) : (
          <div className="mt-6 bg-white/[0.03] border border-white/[0.06] rounded-xl p-4">
            <p className="text-xs font-semibold text-violet-200 mb-2 flex items-center gap-1.5">
              <Monitor size={13} /> {t('Como instalar', 'How to install')}
            </p>
            <ol className="list-decimal pl-4 space-y-1.5 text-[13px] text-violet-100/80">
              {steps[platform].map((s) => <li key={s}>{s}</li>)}
            </ol>
          </div>
        )}

        <Link to="/login" className="mt-5 flex items-center justify-center gap-1.5 text-xs text-violet-300/80 hover:text-violet-200 no-underline">
          <LogIn size={13} /> {t('Prefiro entrar pelo navegador', 'I prefer to sign in on the browser')}
        </Link>
      </div>
    </div>
  )
}
