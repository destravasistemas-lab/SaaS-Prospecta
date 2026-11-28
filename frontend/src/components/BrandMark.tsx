import { useId } from 'react'

/** Logo P do Prospecta. Mesmo desenho dos ícones do app (frontend/public/icon-*.png). */
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
        d="M284 232H564A184 184 0 0 1 564 600H404V792H284ZM404 340H564A76 76 0 0 1 564 492H404Z"
      />
    </svg>
  )
}
