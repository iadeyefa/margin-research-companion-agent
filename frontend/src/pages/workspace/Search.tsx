import { useEffect, useMemo, useRef, useState } from 'react'
import type { FormEvent } from 'react'
import { useParams } from 'react-router-dom'
import { api } from '../../api/client'
import {
  ALL_SOURCE_KEYS,
  SOURCE_OPTIONS,
  paperKey,
  type CollaborativeSearchPlan,
  type Paper,
  type SortOption,
  type SourceKey,
  isSourceKey,
} from '../../api/types'
import { EmptyState } from '../../components/EmptyState'
import { PaperCard } from '../../components/PaperCard'
import { useWorkspaceStore } from '../../state/WorkspaceStore'

type SearchUIMode = 'quick' | 'guided'

const SUGGESTED_QUERIES = [
  'retrieval augmented generation',
  'transformer interpretability',
  'graph neural networks for drug discovery',
  'long-context language models',
]

function sourcesFromPlan(sources: string[]): SourceKey[] {
  const next = sources.filter(isSourceKey)
  return next.length > 0 ? next : [...ALL_SOURCE_KEYS]
}

export function SearchTab() {
  const { workspaceId } = useParams<{ workspaceId: string }>()
  const id = Number(workspaceId)
  const {
    workspaceDetails,
    refreshWorkspace,
    savePaper,
    selection,
    togglePaperSelection,
    isSelected,
    pushToast,
  } = useWorkspaceStore()
  const detail = workspaceDetails[id]

  const [mode, setMode] = useState<SearchUIMode>('quick')
  const [query, setQuery] = useState('')
  const [enabledSources, setEnabledSources] = useState<SourceKey[]>([...ALL_SOURCE_KEYS])
  const [showAdvanced, setShowAdvanced] = useState(false)
  const [yearFrom, setYearFrom] = useState('')
  const [yearTo, setYearTo] = useState('')
  const [limitPerSource, setLimitPerSource] = useState('4')
  const [openAccessOnly, setOpenAccessOnly] = useState(false)
  const [sortBy, setSortBy] = useState<SortOption>('relevance')
  const [results, setResults] = useState<Paper[]>([])
  const [sourceErrors, setSourceErrors] = useState<Record<string, string>>({})
  const [rateLimitedSources, setRateLimitedSources] = useState<SourceKey[]>([])
  const [isSearching, setIsSearching] = useState(false)

  const [guidedMessages, setGuidedMessages] = useState<Array<{ role: 'user' | 'assistant'; content: string }>>([])
  const [guidedDraft, setGuidedDraft] = useState('')
  const [guidedBusy, setGuidedBusy] = useState(false)
  const [guidedCatalogCap, setGuidedCatalogCap] = useState(4)
  const [guidedQuick, setGuidedQuick] = useState<string[]>([])
  const guidedThreadRef = useRef<HTMLDivElement | null>(null)

  useEffect(() => {
    if (!Number.isNaN(id)) void refreshWorkspace(id)
  }, [id, refreshWorkspace])

  useEffect(() => {
    guidedThreadRef.current?.scrollTo({ top: guidedThreadRef.current.scrollHeight, behavior: 'smooth' })
  }, [guidedMessages.length, guidedQuick.length])

  useEffect(() => {
    if (mode !== 'guided' || guidedMessages.length > 0) return

    let live = true
    ;(async () => {
      setGuidedBusy(true)
      setGuidedQuick([])
      try {
        const reply = await api.guidedSearchTurn({
          messages: [],
          desired_catalog_count: guidedCatalogCap,
          workspace_id: Number.isNaN(id) ? null : id,
        })
        if (!live) return
        setGuidedMessages([{ role: 'assistant', content: reply.assistant_message }])
        setGuidedQuick(reply.quick_replies ?? [])
      } catch (caught) {
        if (!live) return
        pushToast(caught instanceof Error ? caught.message : 'Guided search opener failed.', 'error')
      } finally {
        if (live) setGuidedBusy(false)
      }
    })()

    return () => {
      live = false
    }
  }, [mode, guidedMessages.length, id, pushToast])

  const savedKeys = useMemo(
    () => new Set((detail?.saved_papers ?? []).map((paper) => paperKey(paper))),
    [detail?.saved_papers],
  )

  function toggleSource(source: SourceKey) {
    if (rateLimitedSources.includes(source)) return
    setEnabledSources((current) =>
      current.includes(source) ? current.filter((item) => item !== source) : [...current, source],
    )
  }

  function applyPlanToControls(plan: CollaborativeSearchPlan) {
    setQuery(plan.query)
    setEnabledSources(sourcesFromPlan(plan.sources).filter((source) => !rateLimitedSources.includes(source)))
    setLimitPerSource(String(plan.limit_per_source))
    setYearFrom(plan.year_from !== null ? String(plan.year_from) : '')
    setYearTo(plan.year_to !== null ? String(plan.year_to) : '')
    setOpenAccessOnly(plan.open_access_only)
    setSortBy(plan.sort_by)
  }

  async function executeSearch(payload: {
    effectiveQuery: string
    sources: SourceKey[]
    limitPerSrc: number
    year_from: number | null
    year_to: number | null
    open_access: boolean
    sort: SortOption
  }) {
    const effectiveSources = payload.sources.filter((source) => !rateLimitedSources.includes(source))
    if (!payload.effectiveQuery.trim() || effectiveSources.length === 0) return
    setIsSearching(true)
    setSourceErrors({})
    try {
      const response = await api.search({
        query: payload.effectiveQuery.trim(),
        limit_per_source: payload.limitPerSrc,
        sources: effectiveSources,
        workspace_id: Number.isNaN(id) ? null : id,
        year_from: payload.year_from,
        year_to: payload.year_to,
        open_access_only: payload.open_access,
        sort_by: payload.sort,
      })
      setQuery(payload.effectiveQuery.trim())
      setResults(response.results)
      setSourceErrors(response.source_errors ?? {})
      const limited = Object.entries(response.source_errors ?? {})
        .filter(([, message]) => /\b429\b|rate ?limit/i.test(message))
        .map(([source]) => source)
        .filter(isSourceKey)
      if (limited.length > 0) {
        setRateLimitedSources((current) => {
          const merged = [...new Set([...current, ...limited])]
          setEnabledSources((existing) => {
            const next = existing.filter((source) => !merged.includes(source))
            return next
          })
          return merged
        })
        const labels = limited
          .map((key) => SOURCE_OPTIONS.find((option) => option.key === key)?.label ?? key)
          .join(', ')
        pushToast(`Temporarily disabled rate-limited sources: ${labels}.`, 'error')
      }
      void refreshWorkspace(id)
    } catch (caught) {
      pushToast(caught instanceof Error ? caught.message : 'Search failed.', 'error')
    } finally {
      setIsSearching(false)
    }
  }

  async function runSearch(event?: FormEvent, override?: string) {
    event?.preventDefault()
    const effectiveQuery = (override ?? query).trim()
    if (!effectiveQuery || enabledSources.length === 0) return
    await executeSearch({
      effectiveQuery,
      sources: enabledSources,
      limitPerSrc: Number(limitPerSource) || 4,
      year_from: yearFrom ? Number(yearFrom) : null,
      year_to: yearTo ? Number(yearTo) : null,
      open_access: openAccessOnly,
      sort: sortBy,
    })
  }

  function resetGuidedSession() {
    setGuidedMessages([])
    setGuidedDraft('')
    setGuidedQuick([])
  }

  async function submitGuidedUserMessage(textRaw: string) {
    const text = textRaw.trim()
    if (!text || guidedBusy) return

    const nextThread = [...guidedMessages, { role: 'user' as const, content: text }]
    setGuidedMessages(nextThread)
    setGuidedDraft('')
    setGuidedQuick([])
    setGuidedBusy(true)
    try {
      const reply = await api.guidedSearchTurn({
        messages: nextThread,
        desired_catalog_count: guidedCatalogCap,
        workspace_id: Number.isNaN(id) ? null : id,
      })
      const withAssistant = [...nextThread, { role: 'assistant' as const, content: reply.assistant_message }]
      setGuidedMessages(withAssistant)

      if (reply.phase === 'ready' && reply.search) {
        applyPlanToControls(reply.search)
        await executeSearch({
          effectiveQuery: reply.search.query,
          sources: sourcesFromPlan(reply.search.sources),
          limitPerSrc: reply.search.limit_per_source || 5,
          year_from: reply.search.year_from,
          year_to: reply.search.year_to,
          open_access: reply.search.open_access_only,
          sort: reply.search.sort_by,
        })
      } else {
        setGuidedQuick(reply.quick_replies ?? [])
      }
    } catch (caught) {
      pushToast(caught instanceof Error ? caught.message : 'Guided turn failed.', 'error')
      setGuidedMessages((thread) =>
        thread.length > 0 && thread[thread.length - 1]?.role === 'user' ? thread.slice(0, -1) : thread,
      )
    } finally {
      setGuidedBusy(false)
    }
  }

  return (
    <div className="search-tab">
      <div className="search-mode-picker" role="tablist" aria-label="Search mode">
        <button
          type="button"
          className={`search-mode-chip${mode === 'quick' ? ' is-active' : ''}`}
          role="tab"
          aria-selected={mode === 'quick'}
          onClick={() => setMode('quick')}
        >
          Quick search
          <span className="search-mode-hint">You pick catalogs</span>
        </button>
        <button
          type="button"
          className={`search-mode-chip${mode === 'guided' ? ' is-active' : ''}`}
          role="tab"
          aria-selected={mode === 'guided'}
          onClick={() => setMode('guided')}
        >
          Guided search
          <span className="search-mode-hint">Agent asks, then selects catalogs</span>
        </button>
      </div>

      <section className="search-card surface">
        {mode === 'quick' ? (
          <form className="search-form" onSubmit={(event) => void runSearch(event)}>
            <div className="search-input-row">
              <input
                aria-label="Search research publications"
                className="search-input"
                onChange={(event) => setQuery(event.target.value)}
                placeholder="Topic, method, benchmark, or paper family"
                value={query}
              />
              <button
                className="pill-button is-primary"
                disabled={isSearching || !query.trim() || enabledSources.length === 0}
                type="submit"
              >
                {isSearching ? 'Searching…' : 'Search'}
              </button>
            </div>
            <div className="source-row">
              <button
                type="button"
                className="link-button"
                onClick={() =>
                  setEnabledSources(enabledSources.length === ALL_SOURCE_KEYS.length ? [] : [...ALL_SOURCE_KEYS])
                }
              >
                {enabledSources.length === ALL_SOURCE_KEYS.length ? 'Clear all' : 'Select all'}
              </button>
              {rateLimitedSources.length > 0 && (
                <button
                  type="button"
                  className="link-button"
                  onClick={() => setRateLimitedSources([])}
                >
                  Re-enable throttled
                </button>
              )}
              {SOURCE_OPTIONS.map((option) => {
                const active = enabledSources.includes(option.key)
                const throttled = rateLimitedSources.includes(option.key)
                return (
                  <label
                    key={option.key}
                    className={`source-chip${active ? ' is-active' : ''}${throttled ? ' is-disabled' : ''} ${option.tone}`}
                    title={throttled ? 'Temporarily disabled after rate limit. Click "Re-enable throttled" to retry.' : undefined}
                  >
                    <input
                      checked={active}
                      disabled={throttled}
                      onChange={() => toggleSource(option.key)}
                      type="checkbox"
                    />
                    <span>{option.label}</span>
                  </label>
                )
              })}
              <button className="link-button" type="button" onClick={() => setShowAdvanced((value) => !value)}>
                {showAdvanced ? 'Hide filters' : 'More filters'}
              </button>
            </div>
            {showAdvanced && (
              <section className="advanced-grid">
                <label className="field">
                  <span>Year from</span>
                  <input value={yearFrom} onChange={(event) => setYearFrom(event.target.value)} placeholder="e.g. 2020" inputMode="numeric" />
                </label>
                <label className="field">
                  <span>Year to</span>
                  <input value={yearTo} onChange={(event) => setYearTo(event.target.value)} placeholder="e.g. 2026" inputMode="numeric" />
                </label>
                <label className="field">
                  <span>Per source</span>
                  <select value={limitPerSource} onChange={(event) => setLimitPerSource(event.target.value)}>
                    {['3', '4', '5', '7', '10'].map((value) => (
                      <option key={value} value={value}>
                        {value}
                      </option>
                    ))}
                  </select>
                </label>
                <label className="field">
                  <span>Sort by</span>
                  <select value={sortBy} onChange={(event) => setSortBy(event.target.value as SortOption)}>
                    <option value="relevance">Relevance</option>
                    <option value="newest">Newest</option>
                    <option value="most_cited">Most cited</option>
                  </select>
                </label>
                <label className="field field-toggle">
                  <span>Open access only</span>
                  <input checked={openAccessOnly} onChange={(event) => setOpenAccessOnly(event.target.checked)} type="checkbox" />
                </label>
              </section>
            )}
          </form>
        ) : (
          <div className="guided-search">
            <div className="guided-search-toolbar">
              <label className="guided-catalog-cap">
                <span>Maximum catalogs agent may query</span>
                <input
                  aria-label="Maximum number of catalogs"
                  disabled={guidedBusy || isSearching}
                  inputMode="numeric"
                  max={5}
                  min={1}
                  type="number"
                  value={guidedCatalogCap}
                  onChange={(event) =>
                    setGuidedCatalogCap(Math.min(5, Math.max(1, Number(event.target.value) || 4)))
                  }
                />
              </label>
              <button
                className="link-button guided-reset"
                type="button"
                disabled={guidedBusy}
                onClick={() => resetGuidedSession()}
              >
                Restart conversation
              </button>
            </div>

            <p className="guided-search-lede muted">
              The companion asks concise questions—discipline, time window, OA preference—and ends with choosing which
              catalogs to query, up to the limit you set. Your answers steer the agent; it picks the catalogs.
            </p>

            <div ref={guidedThreadRef} className="guided-thread" aria-live="polite">
              {guidedMessages.map((bubble, idx) => (
                <div
                  key={`${idx}-${bubble.role}-${bubble.content.slice(0, 12)}`}
                  className={`guided-bubble${bubble.role === 'assistant' ? ' is-assistant' : ' is-user'}`}
                >
                  <p className="guided-bubble-role">{bubble.role === 'assistant' ? 'Companion' : 'You'}</p>
                  <p className="guided-bubble-body">{bubble.content}</p>
                </div>
              ))}
              {guidedBusy && (
                <p className="guided-thinking muted">{guidedMessages.length === 0 ? 'Starting…' : 'Thinking…'}</p>
              )}
            </div>

            {guidedQuick.length > 0 && (
              <div className="guided-quick-row">
                {guidedQuick.map((chip) => (
                  <button
                    key={chip}
                    className="suggestion-chip"
                    type="button"
                    disabled={guidedBusy}
                    onClick={() => void submitGuidedUserMessage(chip)}
                  >
                    {chip}
                  </button>
                ))}
              </div>
            )}

            <div className="guided-compose">
              <textarea
                aria-label="Your reply to the companion"
                className="guided-textarea"
                disabled={guidedBusy || isSearching}
                placeholder='Reply—or pick a shortcut chip above.'
                rows={3}
                value={guidedDraft}
                onChange={(event) => setGuidedDraft(event.target.value)}
                onKeyDown={(event) => {
                  if (event.key === 'Enter' && (event.metaKey || event.ctrlKey)) {
                    event.preventDefault()
                    void submitGuidedUserMessage(guidedDraft)
                  }
                }}
              />
              <button
                className="pill-button is-primary"
                disabled={guidedBusy || isSearching || !guidedDraft.trim()}
                type="button"
                onClick={() => void submitGuidedUserMessage(guidedDraft)}
              >
                {guidedBusy ? 'Sending…' : 'Send reply'}
              </button>
            </div>
          </div>
        )}
      </section>

      {Object.keys(sourceErrors).length > 0 && (
        <section className="surface error-surface">
          <p className="surface-eyebrow">Some sources had issues</p>
          {Object.entries(sourceErrors).map(([source, message]) => {
            const cleanedMessage = message.replace(/https?:\/\/\S+/g, '').replace(/\s+/g, ' ').trim()
            const sourceLabel = SOURCE_OPTIONS.find((option) => option.key === source)?.label ?? source
            const isRateLimit = /\b429\b|rate ?limit/i.test(cleanedMessage)
            return (
              <p key={source}>
                <strong>{sourceLabel}:</strong>{' '}
                {isRateLimit
                  ? 'rate limit reached — try again in a moment, or deselect this source.'
                  : cleanedMessage || 'request failed.'}
              </p>
            )
          })}
        </section>
      )}

      <section className="search-results-section">
        <div className="surface-header">
          <div>
            <p className="surface-eyebrow">Results</p>
            <h2 className="surface-title">
              {results.length > 0 ? `${results.length} papers across ${new Set(results.map((paper) => paper.source)).size} sources` : 'Run a search'}
            </h2>
          </div>
          {results.length > 0 && (
            <p className="muted">{selection.papers.length} selected for synthesis</p>
          )}
        </div>
        {results.length === 0 ? (
          <EmptyState
            size="lg"
            title="No results yet"
            description={
              mode === 'quick' ? (
                <>
                  Try a topic or paper family. Try one of these to get started:
                  <span className="suggestion-chip-row">
                    {SUGGESTED_QUERIES.map((suggestion) => (
                      <button
                        key={suggestion}
                        className="suggestion-chip"
                        type="button"
                        onClick={() => {
                          setQuery(suggestion)
                          void executeSearch({
                            effectiveQuery: suggestion,
                            sources: enabledSources,
                            limitPerSrc: Number(limitPerSource) || 4,
                            year_from: yearFrom ? Number(yearFrom) : null,
                            year_to: yearTo ? Number(yearTo) : null,
                            open_access: openAccessOnly,
                            sort: sortBy,
                          })
                        }}
                      >
                        {suggestion}
                      </button>
                    ))}
                  </span>
                </>
              ) : (
                <>Answer the companion’s prompts; when it’s confident, results land here automatically.</>
              )
            }
          />
        ) : (
          <div className="card-list">
            {results.map((paper) => (
              <PaperCard
                key={paperKey(paper)}
                paper={paper}
                isSelected={isSelected(paper)}
                isSaved={savedKeys.has(paperKey(paper))}
                onToggleSelect={(item) => togglePaperSelection(id, item)}
                onSave={(item) => void savePaper(id, item)}
              />
            ))}
          </div>
        )}
      </section>
    </div>
  )
}
