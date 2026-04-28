import { SOURCE_OPTIONS } from '../api/types'

const TONE_BY_SOURCE: Record<string, string> = SOURCE_OPTIONS.reduce(
  (accumulator, option) => {
    accumulator[option.key] = option.tone
    return accumulator
  },
  {} as Record<string, string>,
)

const LABEL_BY_SOURCE: Record<string, string> = SOURCE_OPTIONS.reduce(
  (accumulator, option) => {
    accumulator[option.key] = option.label
    return accumulator
  },
  {} as Record<string, string>,
)

export function SourceTag({ source }: { source: string }) {
  const tone = TONE_BY_SOURCE[source] ?? 'tone-slate'
  const label = LABEL_BY_SOURCE[source] ?? source
  return <span className={`source-pill ${tone}`}>{label}</span>
}
