import { useTheme } from '../state/ThemeProvider'
import type { ThemeMode } from '../state/ThemeProvider'

const OPTIONS: Array<{ value: ThemeMode; label: string; icon: string }> = [
  { value: 'light', label: 'Light', icon: '☀' },
  { value: 'system', label: 'System', icon: '◐' },
  { value: 'dark', label: 'Dark', icon: '☾' },
]

export function ThemeToggle({ compact = false }: { compact?: boolean }) {
  const { mode, setMode, resolved } = useTheme()

  if (compact) {
    return (
      <button
        type="button"
        className="icon-button theme-icon-button"
        aria-label={`Switch to ${resolved === 'dark' ? 'light' : 'dark'} mode`}
        title={`Theme: ${mode}${mode === 'system' ? ` (${resolved})` : ''}`}
        onClick={() => {
          if (mode === 'system') setMode(resolved === 'dark' ? 'light' : 'dark')
          else setMode(mode === 'dark' ? 'light' : 'dark')
        }}
      >
        {resolved === 'dark' ? '☾' : '☀'}
      </button>
    )
  }

  return (
    <div role="radiogroup" aria-label="Theme" className="theme-toggle">
      {OPTIONS.map((option) => (
        <button
          key={option.value}
          role="radio"
          type="button"
          aria-checked={mode === option.value}
          className={`theme-toggle-option${mode === option.value ? ' is-active' : ''}`}
          title={`Theme: ${option.label}`}
          onClick={() => setMode(option.value)}
        >
          <span aria-hidden="true">{option.icon}</span>
          <span className="theme-toggle-label">{option.label}</span>
        </button>
      ))}
    </div>
  )
}
