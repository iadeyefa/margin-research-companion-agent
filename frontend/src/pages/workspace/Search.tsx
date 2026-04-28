import { useEffect, useMemo, useState } from 'react'
import type { FormEvent } from 'react'
import { useParams } from 'react-router-dom'
import { api } from '../../api/client'
import {
  ALL_SOURCE_KEYS,
  SOURCE_OPTIONS,
  paperKey,
  type Paper,
  type SortOption,
  type SourceKey,
} from '../../api/types'
import { EmptyState } from '../../components/EmptyState'
import { PaperCard } from '../../components/PaperCard'
import { useWorkspaceStore } from '../../state/WorkspaceStore'

const SUGGESTED_QUERIES = [
  'retrieval augmented generation',
  'transformer interpretability',
  'graph neural networks for drug discovery',
  'long-context language models',
]

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
  const [isSearching, setIsSearching] = useState(false)

  useEffect(() => {
    if (!Number.isNaN(id)) void refreshWorkspace(id)
  }, [id, refreshWorkspace])

  const savedKeys = useMemo(
    () => new Set((detail?.saved_papers ?? []).map((paper) => paperKey(paper))),
    [detail?.saved_papers],
  )

  function toggleSource(source: SourceKey) {
    setEnabledSources((current) =>
      current.includes(source) ? current.filter((item) => item !== source) : [...current, source],
    )
  }

  async function runSearch(event?: FormEvent, override?: string) {
    event?.preventDefault()
    const effectiveQuery = (override ?? query).trim()
    if (!effectiveQuery || enabledSources.length === 0) return
    setIsSearching(true)
    setSourceErrors({})
    try {
      const response = await api.search({
        query: effectiveQuery,
        limit_per_source: Number(limitPerSource) || 4,
        sources: enabledSources,
        workspace_id: id,
        year_from: yearFrom ? Number(yearFrom) : null,
        year_to: yearTo ? Number(yearTo) : null,
        open_access_only: openAccessOnly,
        sort_by: sortBy,
      })
      setQuery(effectiveQuery)
      setResults(response.results)
      setSourceErrors(response.source_errors ?? {})
      void refreshWorkspace(id)
    } catch (caught) {
      pushToast(caught instanceof Error ? caught.message : 'Search failed.', 'error')
    } finally {
      setIsSearching(false)
    }
  }

  return (
    <div className="search-tab">
      <section className="search-card surface">
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
            {SOURCE_OPTIONS.map((option) => {
              const active = enabledSources.includes(option.key)
              return (
                <label key={option.key} className={`source-chip${active ? ' is-active' : ''} ${option.tone}`}>
                  <input
                    checked={active}
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
      </section>

      {Object.keys(sourceErrors).length > 0 && (
        <section className="surface error-surface">
          {Object.entries(sourceErrors).map(([source, message]) => (
            <p key={source}>
              <strong>{source}:</strong> {message}
            </p>
          ))}
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
                        void runSearch(undefined, suggestion)
                      }}
                    >
                      {suggestion}
                    </button>
                  ))}
                </span>
              </>
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
