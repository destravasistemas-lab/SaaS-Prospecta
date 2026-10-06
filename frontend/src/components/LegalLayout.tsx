import type { ReactNode } from 'react'
import { Link } from 'react-router-dom'
import { BRANDING } from '../config/branding'
import { LanguageToggle, useI18n } from '../i18n'

export default function LegalLayout({ title, updated, children }: { title: string; updated?: string; children: ReactNode }) {
  const { t } = useI18n()
  return (
    <div className="min-h-screen bg-[#030712] text-[#e2e8f0]">
      <header className="border-b border-white/[0.06]">
        <div className="max-w-3xl mx-auto px-4 sm:px-6 py-4 flex items-center justify-between gap-4">
          <Link to="/" className="flex items-center gap-2">
            <div className="w-7 h-7 rounded-lg bg-gradient-to-br from-[#0284c7] to-[#38bdf8] flex items-center justify-center">
              <span className="text-white font-bold text-xs">P</span>
            </div>
            <span className="text-sm font-semibold text-white">{BRANDING.name}</span>
          </Link>
          <LanguageToggle compact />
        </div>
      </header>

      <main className="max-w-3xl mx-auto px-4 sm:px-6 py-10 space-y-8">
        <div>
          <h1 className="text-3xl font-bold text-white">{title}</h1>
          <p className="text-[#64748b] text-sm mt-2">
            {BRANDING.name} — {BRANDING.companyFullName}
            {updated && <> · {t('Última atualização', 'Last updated')}: {updated}</>}
          </p>
        </div>
        {children}
      </main>

      <footer className="border-t border-white/[0.06]">
        <div className="max-w-3xl mx-auto px-4 sm:px-6 py-6 flex flex-wrap gap-x-6 gap-y-2 text-xs text-[#64748b]">
          <Link to="/privacy" className="hover:text-white">{t('Política de Privacidade', 'Privacy Policy')}</Link>
          <Link to="/terms" className="hover:text-white">{t('Termos de Serviço', 'Terms of Service')}</Link>
          <Link to="/data-deletion" className="hover:text-white">{t('Exclusão de Dados', 'Data Deletion')}</Link>
          <a href={`mailto:${BRANDING.supportEmail}`} className="hover:text-white">{BRANDING.supportEmail}</a>
        </div>
      </footer>
    </div>
  )
}

export function LegalSection({ title, children }: { title: string; children: ReactNode }) {
  return (
    <section className="space-y-3">
      <h2 className="text-lg font-semibold text-white">{title}</h2>
      <div className="text-[#94a3b8] text-sm leading-relaxed space-y-3">{children}</div>
    </section>
  )
}
