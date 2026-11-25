import { AlertTriangle } from 'lucide-react'
import { useI18n } from '../i18n'

export function useOptInRiskText() {
  const { t } = useI18n()
  return t(
    'A Meta exige opt-in para mensagens iniciadas pela empresa. Sem ele, quem recebe tende a bloquear ou denunciar: a qualidade do número cai, o limite diário de envios diminui e a Meta pode restringir ou banir o número (às vezes a conta do WhatsApp Business inteira). Pela LGPD, a responsabilidade pelo contato sem consentimento é da empresa que envia.',
    'Meta requires opt-in for business-initiated messages. Without it, recipients tend to block or report you: the number\'s quality drops, its daily sending limit shrinks and Meta may restrict or ban the number (sometimes the whole WhatsApp Business account). Under data protection law, the sending business is responsible for contacting people without consent.',
  )
}

export default function OptInRisk({ title, message, checked, onChange, label }: {
  title: string
  message?: string
  checked: boolean
  onChange: (v: boolean) => void
  label: string
}) {
  const fallback = useOptInRiskText()
  return (
    <div className="bg-amber-900/15 border border-amber-500/25 rounded-lg px-3 py-2.5 mb-3">
      <p className="flex items-center gap-1.5 text-xs font-semibold text-amber-300 mb-1">
        <AlertTriangle size={13} /> {title}
      </p>
      <p className="text-[11px] text-amber-200/80 leading-relaxed mb-2">{message || fallback}</p>
      <label className="flex items-start gap-2 text-[11px] text-amber-100 cursor-pointer">
        <input type="checkbox" checked={checked} onChange={(e) => onChange(e.target.checked)} className="mt-0.5 accent-amber-500" />
        <span>{label}</span>
      </label>
    </div>
  )
}
