import { useCallback, useEffect, useMemo, useState } from 'react'
import { Link } from 'react-router-dom'
import { api } from '../api/client'
import type { LibraryPaper } from '../api/types'
import { EmptyState } from '../components/EmptyState'
import { PageLoading } from '../components/PageLoading'
import { PageHeader } from '../components/PageHeader'
import { SourceTag } from '../components/SourceTag'
import { useWorkspaceStore } from '../state/WorkspaceStore'

type SortKey = 'recent' | 'newest' | 'most_cited' | 'title'

export function LibraryPage() {
  const { workspaces, removePaper, pushToast } = useWorkspaceStore()
  const [papers, setPapers] = useState<LibraryPaper[]>([])
  const [loading, setLoading] = useState(true)
  const [loadError, setLoadError] = useState<string | null>(null)
  const [search, setSearch] = useState('')
  const [workspaceFilter, setWorkspaceFilter] = useState<'all' | number>('all')
  const [sourceFilter, setSourceFilter] = useState('all')
  const [openAccessOnly, setOpenAccessOnly] = useState(false)
  const [sort, setSort] = useState<SortKey>('recent')

  const reload = useCallback(async () => {
    setLoading(true)
    setLoadError(null)
    try {
      const data = await api.listLibrary()
      setPapers(data)
    } catch (caught) {
      const message = caught instanceof Error ? caught.message : 'Failed to load library.'
      setLoadError(message)
      pushToast(message, 'error')
    } finally {
      setLoading(false)
    }
  }, [pushToast])

  useEffect(() => {
    void reload()
  }, [reload, workspaces.length])

  const sources = useMemo(() => Array.from(new Set(papers.map((paper) => paper.source))), [papers])

  const filtered = useMemo(() => {
    let list = papers
    const lower = search.trim().toLowerCase()
    if (lower) {
      list = list.filter((paper) => {
        return (
          paper.title.toLowerCase().includes(lower) ||
          (paper.abstract ?? '').toLowerCase().includes(lower) ||
          paper.authors.some((author) => author.toLowerCase().includes(lower)) ||
          paper.workspace_title.toLowerCase().includes(lower)
        )
      })
    }
    if (workspaceFilter !== 'all') list = list.filter((paper) => paper.workspace_id === workspaceFilter)
    if (sourceFilter !== 'all') list = list.filter((paper) => paper.source === sourceFilter)
    if (openAccessOnly) list = list.filter((paper) => paper.open_access)
    const sorted = [...list]
    if (sort === 'newest') {
      sorted.sort((a, b) => (b.year ?? -Infinity) - (a.year ?? -Infinity))
    } else if (sort === 'most_cited') {
      sorted.sort((a, b) => (b.citation_count ?? -1) - (a.citation_count ?? -1))
    } else if (sort === 'title') {
      sorted.sort((a, b) => a.title.localeCompare(b.title))
    } else {
      sorted.sort((a, b) => new Date(b.saved_at).getTime() - new Date(a.saved_at).getTime())
    }
    return sorted
  }, [openAccessOnly, papers, search, sort, sourceFilter, workspaceFilter])

  return (
    <div className="page page-library">
      <PageHeader
        eyebrow="Library"
        title="Saved papers across all workspaces"
        description="Browse, filter, and re-discover everything you have collected."
      />

      <section className="surface library-controls">
        <input
          className="search-input"
          placeholder="Search by title, author, abstract, or workspace…"
          value={search}
          onChange={(event) => setSearch(event.target.value)}
        />
        <div className="filter-row">
          <label className="field-inline">
            <span>Workspace</span>
            <select
              value={workspaceFilter === 'all' ? 'all' : String(workspaceFilter)}
              onChange={(event) => {
                const value = event.target.value
                setWorkspaceFilter(value === 'all' ? 'all' : Number(value))
              }}
            >
              <option value="all">All workspaces</option>
              {workspaces.map((workspace) => (
                <option key={workspace.id} value={String(workspace.id)}>
                  {workspace.title}
                </option>
              ))}
            </select>
          </label>
          <label className="field-inline">
            <span>Source</span>
            <select value={sourceFilter} onChange={(event) => setSourceFilter(event.target.value)}>
              <option value="all">All sources</option>
              {sources.map((source) => (
                <option key={source} value={source}>
                  {source}
                </option>
              ))}
            </select>
          </label>
          <label className="field-inline">
            <span>Sort</span>
            <select value={sort} onChange={(event) => setSort(event.target.value as SortKey)}>
              <option value="recent">Recently saved</option>
              <option value="newest">Newest publication</option>
              <option value="most_cited">Most cited</option>
              <option value="title">Title (A → Z)</option>
            </select>
          </label>
          <label className="field-inline field-toggle">
            <input checked={openAccessOnly} onChange={(event) => setOpenAccessOnly(event.target.checked)} type="checkbox" />
            <span>Open access only</span>
          </label>
        </div>
      </section>

      <section className="library-section">
        <div className="surface-header library-meta-row">
          {loading ? (
            <PageLoading message="Fetching saved papers…" dense />
          ) : (
            <p className="muted">
              {filtered.length} of {papers.length} {papers.length === 1 ? 'paper' : 'papers'}
            </p>
          )}
        </div>
        {loadError && (
          <div className="library-error-banner" role="alert">
            <span>
              <strong>Could not reach the API.</strong> {loadError} Make sure the backend is running on port 3000.
            </span>
            <button type="button" className="pill-button is-primary" onClick={() => void reload()}>
              Retry
            </button>
          </div>
        )}
        {loading ? (
          <div className="library-skeleton-stack" aria-hidden>
            {[0, 1, 2, 3].map((i) => (
              <div key={i} className="library-skeleton-card">
                <span className="ui-shimmer-bar" />
                <span className="ui-shimmer-bar" />
                <span className="ui-shimmer-bar" />
                <span className="ui-shimmer-bar" />
              </div>
            ))}
          </div>
        ) : loadError ? null : filtered.length === 0 ? (
          <EmptyState
            size="lg"
            title={papers.length === 0 ? 'Your library is empty' : 'No papers match these filters'}
            description={
              papers.length === 0
                ? 'Save papers in any workspace to populate your library.'
                : 'Try clearing a filter or broadening your search.'
            }
          />
        ) : (
          <div className="card-list">
            {filtered.map((paper) => (
              <article key={`${paper.source}-${paper.external_id}-${paper.workspace_id}`} className="paper-card library-card">
                <div className="paper-card-header">
                  <SourceTag source={paper.source} />
                  {paper.year && <span className="paper-year">{paper.year}</span>}
                  {paper.citation_count != null && paper.citation_count > 0 && (
                    <span className="paper-pill">{paper.citation_count.toLocaleString()} cited</span>
                  )}
                  {paper.open_access && <span className="paper-pill paper-pill-accent">Open access</span>}
                  <span className="paper-pill paper-pill-muted">{paper.workspace_title}</span>
                </div>
                <h3 className="paper-title">
                  <Link
                    to={`/papers/${encodeURIComponent(paper.source)}/${encodeURIComponent(paper.external_id)}`}
                    state={{ paper, workspaceId: paper.workspace_id }}
                  >
                    {paper.title}
                  </Link>
                </h3>
                <p className="paper-meta">
                  {paper.authors.slice(0, 5).join(', ') || 'Unknown authors'}
                  {paper.venue ? ` · ${paper.venue}` : ''}
                </p>
                {paper.abstract && <p className="paper-abstract clamp-3">{paper.abstract}</p>}
                <div className="paper-actions">
                  <Link
                    className="pill-button is-ghost"
                    to={`/workspaces/${paper.workspace_id}/overview`}
                  >
                    Open workspace
                  </Link>
                  {paper.url && (
                    <a className="pill-button is-ghost" href={paper.url} rel="noreferrer" target="_blank">
                      Source
                    </a>
                  )}
                  {paper.pdf_url && (
                    <a className="pill-button is-ghost" href={paper.pdf_url} rel="noreferrer" target="_blank">
                      PDF
                    </a>
                  )}
                  <button
                    className="pill-button is-ghost"
                    type="button"
                    onClick={async () => {
                      await removePaper(paper.workspace_id, paper)
                      void reload()
                    }}
                  >
                    Remove
                  </button>
                </div>
              </article>
            ))}
          </div>
        )}
      </section>
    </div>
  )
}
