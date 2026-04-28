import { createContext, useCallback, useContext, useEffect, useMemo, useState } from 'react'
import type { ReactNode } from 'react'

export type ThemeMode = 'system' | 'light' | 'dark'
type ResolvedTheme = 'light' | 'dark'

type ThemeValue = {
  mode: ThemeMode
  resolved: ResolvedTheme
  setMode: (next: ThemeMode) => void
  toggle: () => void
}

const STORAGE_KEY = 'rc-theme'
const ThemeContext = createContext<ThemeValue | null>(null)

function readStoredMode(): ThemeMode {
  if (typeof window === 'undefined') return 'system'
  const value = window.localStorage.getItem(STORAGE_KEY)
  if (value === 'light' || value === 'dark' || value === 'system') return value
  return 'system'
}

function systemPrefersDark(): boolean {
  if (typeof window === 'undefined' || !window.matchMedia) return false
  return window.matchMedia('(prefers-color-scheme: dark)').matches
}

function resolve(mode: ThemeMode): ResolvedTheme {
  if (mode === 'system') return systemPrefersDark() ? 'dark' : 'light'
  return mode
}

function applyTheme(resolved: ResolvedTheme) {
  if (typeof document === 'undefined') return
  document.documentElement.dataset.theme = resolved
  document.documentElement.style.colorScheme = resolved
}

export function ThemeProvider({ children }: { children: ReactNode }) {
  const [mode, setModeState] = useState<ThemeMode>(() => readStoredMode())
  const [resolved, setResolved] = useState<ResolvedTheme>(() => resolve(readStoredMode()))

  useEffect(() => {
    const next = resolve(mode)
    setResolved(next)
    applyTheme(next)
    if (typeof window !== 'undefined') {
      window.localStorage.setItem(STORAGE_KEY, mode)
    }
  }, [mode])

  useEffect(() => {
    if (mode !== 'system' || typeof window === 'undefined' || !window.matchMedia) return
    const media = window.matchMedia('(prefers-color-scheme: dark)')
    const listener = () => {
      const next: ResolvedTheme = media.matches ? 'dark' : 'light'
      setResolved(next)
      applyTheme(next)
    }
    media.addEventListener('change', listener)
    return () => media.removeEventListener('change', listener)
  }, [mode])

  const setMode = useCallback((next: ThemeMode) => {
    setModeState(next)
  }, [])

  const toggle = useCallback(() => {
    setModeState((current) => {
      if (current === 'system') return resolve('system') === 'dark' ? 'light' : 'dark'
      return current === 'dark' ? 'light' : 'dark'
    })
  }, [])

  const value = useMemo<ThemeValue>(() => ({ mode, resolved, setMode, toggle }), [mode, resolved, setMode, toggle])

  return <ThemeContext.Provider value={value}>{children}</ThemeContext.Provider>
}

export function useTheme() {
  const value = useContext(ThemeContext)
  if (!value) throw new Error('useTheme must be used inside ThemeProvider')
  return value
}
