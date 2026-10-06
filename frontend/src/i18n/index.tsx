import { createContext, useCallback, useContext, useEffect, useMemo, useState, type ReactNode } from 'react'

export type Lang = 'pt' | 'en'

const STORAGE_KEY = 'lang'

function detectLang(): Lang {
  try {
    const saved = localStorage.getItem(STORAGE_KEY)
    if (saved === 'pt' || saved === 'en') return saved
  } catch {
    /* storage unavailable */
  }
  const nav = typeof navigator !== 'undefined' ? navigator.language || '' : ''
  return nav.toLowerCase().startsWith('pt') ? 'pt' : 'en'
}

let currentLang: Lang = detectLang()

/** Current language outside React (used by the API client to send X-Lang). */
export function getLang(): Lang {
  return currentLang
}

/** Non-hook translation for code that runs outside components. */
export function tr(pt: string, en: string): string {
  return currentLang === 'en' ? en : pt
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
    document.documentElement.lang = lang === 'pt' ? 'pt-BR' : 'en'
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
    locale: lang === 'pt' ? 'pt-BR' : 'en-US',
    setLang,
    t: (pt: string, en: string) => (lang === 'en' ? en : pt),
  }), [lang, setLang])

  return <I18nContext.Provider value={value}>{children}</I18nContext.Provider>
}

export function useI18n(): I18nValue {
  const ctx = useContext(I18nContext)
  if (!ctx) throw new Error('useI18n must be used inside <LanguageProvider>')
  return ctx
}

export function LanguageToggle({ className = '', compact = false }: { className?: string; compact?: boolean }) {
  const { lang, setLang, t } = useI18n()
  const options: { code: Lang; label: string; flag: string }[] = [
    { code: 'en', label: 'English', flag: '🇺🇸' },
    { code: 'pt', label: 'Português', flag: '🇧🇷' },
  ]
  return (
    <div
      role="group"
      aria-label={t('Idioma', 'Language')}
      className={`inline-flex items-center rounded-lg border border-white/10 bg-white/[0.03] p-0.5 text-xs ${className}`}
    >
      {options.map((o) => (
        <button
          key={o.code}
          type="button"
          onClick={() => setLang(o.code)}
          aria-pressed={lang === o.code}
          title={o.label}
          className={`flex items-center gap-1 rounded-md px-2 py-1 font-medium transition-colors ${
            lang === o.code ? 'bg-sky-500/20 text-sky-200' : 'text-[#64748b] hover:text-white'
          }`}
        >
          <span aria-hidden>{o.flag}</span>
          {compact ? o.code.toUpperCase() : o.label}
        </button>
      ))}
    </div>
  )
}
