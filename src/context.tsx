import { createContext, useCallback, useContext, useEffect, useMemo, useState } from 'react'
import type { ReactNode } from 'react'
import copyDefault from './i18n/copy'
import type { Lang, Copy } from './i18n/copy'

type Theme = 'dark' | 'light'

interface AppState {
  theme: Theme
  toggleTheme: () => void
  lang: Lang
  setLang: (l: Lang) => void
  t: Copy
}

const AppCtx = createContext<AppState | null>(null)

function initialTheme(): Theme {
  const boot = document.documentElement.dataset.theme
  return boot === 'light' ? 'light' : 'dark'
}

function initialLang(): Lang {
  try {
    return localStorage.getItem('lang') === 'en' ? 'en' : 'id'
  } catch {
    return 'id'
  }
}

export function AppProvider({ children }: { children: ReactNode }) {
  const [theme, setTheme] = useState<Theme>(initialTheme)
  const [lang, setLangState] = useState<Lang>(initialLang)

  useEffect(() => {
    document.documentElement.dataset.theme = theme
    try {
      localStorage.setItem('theme', theme)
    } catch { /* private mode */ }
  }, [theme])

  const setLang = useCallback((l: Lang) => {
    setLangState(l)
    document.documentElement.lang = l
    try {
      localStorage.setItem('lang', l)
    } catch { /* private mode */ }
  }, [])

  useEffect(() => {
    document.documentElement.lang = lang
  }, [lang])

  const value = useMemo<AppState>(
    () => ({
      theme,
      toggleTheme: () => setTheme((v) => (v === 'dark' ? 'light' : 'dark')),
      lang,
      setLang,
      t: copyDefault[lang],
    }),
    [theme, lang, setLang],
  )

  return <AppCtx.Provider value={value}>{children}</AppCtx.Provider>
}

export function useApp() {
  const ctx = useContext(AppCtx)
  if (!ctx) throw new Error('useApp harus dipakai di dalam AppProvider')
  return ctx
}
