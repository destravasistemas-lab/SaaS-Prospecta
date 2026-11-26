import { useId } from 'react'

/** Logo DP: o D da Destrava com o P do Prospecta dentro, dividindo a haste. Mesmo desenho dos ícones do app. */
export default function BrandMark({ className = 'w-8 h-8' }: { className?: string }) {
  const id = useId()
  return (
    <svg viewBox="0 0 1024 1024" className={`shrink-0 ${className}`} role="img" aria-label="Prospecta">
      <defs>
        <linearGradient id={`${id}-bg`} x1="0" y1="0" x2="1" y2="1">
          <stop offset="0" stopColor="#6d28d9" />
          <stop offset="0.55" stopColor="#c026d3" />
          <stop offset="1" stopColor="#f97316" />
        </linearGradient>
      </defs>
      <rect width="1024" height="1024" rx="230" fill={`url(#${id}-bg)`} />
      <path
        fillRule="evenodd"
        fill="#fff"
        d="M276 232H548A200 280 0 0 1 548 792H276ZM360 316H548A116 196 0 0 1 548 708H360Z"
      />
      <path
        fillRule="evenodd"
        fill="#ffd6a5"
        d="M360 372H488A120 120 0 0 1 488 612H360ZM360 432H488A60 60 0 0 1 488 552H360Z"
      />
    </svg>
  )
}
