import { createContext, useCallback, useContext, useEffect, useMemo, useState, type ReactNode } from 'react'
import { ES } from './es'

export type Lang = 'pt' | 'en' | 'es'

const LOCALES: Record<Lang, string> = { pt: 'pt-BR', en: 'en-US', es: 'es' }

// Espanhol: dicionário indexado pelo texto em português. Textos com trechos
// variáveis ({0}, {1}…) viram padrões; sem tradução, cai no português.
const esExact = new Map<string, string>()
const esPatterns: [RegExp, string][] = []
for (const [pt, es] of Object.entries(ES)) {
  if (!/\{\d+\}/.test(pt)) {
    esExact.set(pt, es)
    continue
  }
  if (pt.replace(/\{\d+\}/g, '').trim().length < 2) continue
  const source = pt
    .split(/(\{\d+\})/)
    .map((part) => (/^\{\d+\}$/.test(part) ? '([\\s\\S]*?)' : part.replace(/[.*+?^${}()|[\]\\]/g, '\\$&')))
    .join('')
  esPatterns.push([new RegExp(`^${source}$`), es])
}
const esCache = new Map<string, string>()

export function toSpanish(pt: string): string {
  const exact = esExact.get(pt)
  if (exact !== undefined) return exact
  const cached = esCache.get(pt)
  if (cached !== undefined) return cached
  let out = pt
  for (const [re, es] of esPatterns) {
    const m = re.exec(pt)
    if (m) {
      out = es.replace(/\{(\d+)\}/g, (_, i) => m[Number(i) + 1] ?? '')
      break
    }
  }
  if (esCache.size < 5000) esCache.set(pt, out)
  return out
}

function pick(lang: Lang, pt: string, en: string): string {
  if (lang === 'en') return en
  if (lang === 'es') return toSpanish(pt)
  return pt
}

const STORAGE_KEY = 'lang'

function detectLang(): Lang {
  try {
    const saved = localStorage.getItem(STORAGE_KEY)
    if (saved === 'pt' || saved === 'en' || saved === 'es') return saved
  } catch {
    /* storage unavailable */
  }
  const nav = typeof navigator !== 'undefined' ? navigator.language || '' : ''
  const code = nav.toLowerCase()
  if (code.startsWith('pt')) return 'pt'
  if (code.startsWith('es')) return 'es'
  return 'en'
}

let currentLang: Lang = detectLang()

/** Current language outside React (used by the API client to send X-Lang). */
export function getLang(): Lang {
  return currentLang
}

/** Non-hook translation for code that runs outside components. */
export function tr(pt: string, en: string): string {
  return pick(currentLang, pt, en)
}

interface I18nValue {
  lang: Lang
  locale: string
  setLang: (lang: Lang) => void
  t: (pt: string, en: string) => string
}

const I18nContext = createContext<I18nValue | null>(null)

export function LanguageProvider({ children }: { children: ReactNode }) {
  const [lang, setLangState] = useState<Lang>(currentLang)

  useEffect(() => {
    currentLang = lang
    document.documentElement.lang = LOCALES[lang]
    try {
      localStorage.setItem(STORAGE_KEY, lang)
    } catch {
      /* storage unavailable */
    }
  }, [lang])

  const setLang = useCallback((next: Lang) => {
    currentLang = next
    setLangState(next)
  }, [])

  const value = useMemo<I18nValue>(() => ({
    lang,
    locale: LOCALES[lang],
    setLang,
    t: (pt: string, en: string) => pick(lang, pt, en),
  }), [lang, setLang])

  return <I18nContext.Provider value={value}>{children}</I18nContext.Provider>
}

export function useI18n(): I18nValue {
  const ctx = useContext(I18nContext)
  if (!ctx) throw new Error('useI18n must be used inside <LanguageProvider>')
  return ctx
}

export function LanguageToggle({ className = '', compact = false, light = false }: { className?: string; compact?: boolean; light?: boolean }) {
  const { lang, setLang, t } = useI18n()
  const options: { code: Lang; label: string; flag: string }[] = [
    { code: 'en', label: 'English', flag: '🇺🇸' },
    { code: 'pt', label: 'Português', flag: '🇧🇷' },
    { code: 'es', label: 'Español', flag: '🇪🇸' },
  ]
  return (
    <div
      role="group"
      aria-label={t('Idioma', 'Language')}
      className={`inline-flex items-center rounded-lg border p-0.5 text-xs ${
        light ? 'border-slate-200 bg-slate-50' : 'border-white/10 bg-white/[0.03]'
      } ${className}`}
    >
      {options.map((o) => (
        <button
          key={o.code}
          type="button"
          onClick={() => setLang(o.code)}
          aria-pressed={lang === o.code}
          title={o.label}
          className={`flex items-center gap-1 rounded-md px-2 py-1 font-medium transition-colors ${
            light
              ? lang === o.code ? 'bg-white text-slate-900 shadow-sm' : 'text-slate-500 hover:text-slate-900'
              : lang === o.code ? 'bg-violet-500/20 text-violet-200' : 'text-ink-4 hover:text-white'
          }`}
        >
          <span aria-hidden>{o.flag}</span>
          {compact ? o.code.toUpperCase() : o.label}
        </button>
      ))}
    </div>
  )
}
