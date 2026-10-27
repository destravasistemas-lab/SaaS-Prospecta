import { BRANDING } from '../config/branding'

/** Razão social, CNPJ e endereço — exibidos no rodapé de todas as páginas públicas. */
export default function LegalEntity({ className = '' }: { className?: string }) {
  return (
    <p className={className}>
      {BRANDING.legalName} — CNPJ {BRANDING.cnpj}
      <br />
      {BRANDING.address}
    </p>
  )
}
