import { Link } from 'react-router-dom'
import { HelpCircle } from 'lucide-react'
import { useI18n } from '../i18n'

/** Atalho "Como funciona?" que abre o guia do sistema na seção da funcionalidade. */
export default function HelpLink({ section, className = '' }: { section: string; className?: string }) {
  const { t } = useI18n()
  return (
    <Link
      to={`/app/guia#${section}`}
      className={`inline-flex items-center gap-1 text-xs font-medium text-violet-300/90 hover:text-violet-200 ${className}`}
    >
      <HelpCircle size={13} /> {t('Como funciona?', 'How does it work?')}
    </Link>
  )
}
