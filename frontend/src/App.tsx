import { useEffect, useMemo, useState } from 'react'
import type { ChangeEvent, FormEvent } from 'react'
import './App.css'

type SourceKey = 'crossref' | 'semantic_scholar' | 'openalex' | 'pubmed' | 'arxiv'

type Paper = {
  source: string
  external_id: string
  title: string
  abstract: string | null
  authors: string[]
  venue: string | null
  year: number | null
  publication_date: string | null
  doi: string | null
  url: string | null
  pdf_url: string | null
  citation_count: number | null
  open_access: boolean | null
}

type SearchResponse = {
  query: string
  results: Paper[]
  source_errors: Record<string, string>
}

type SortOption = 'relevance' | 'newest' | 'most_cited'

type ExportResponse = {
  format: string
  content: string
}

type ReadingPathStep = {
  order: number
  title: string
  source: string
  external_id: string
  rationale: string
}

type ReadingPathResponse = {
  objective: string
  overview: string
  steps: ReadingPathStep[]
}

type SearchHistory = {
  id: number
  query: string
  sources: string[]
  result_count: number
  created_at: string
}

type WorkspaceSummary = {
  id: number
  title: string
  notes: string
  saved_paper_count: number
  search_count: number
  created_at: string
  updated_at: string
}

type WorkspaceDetail = WorkspaceSummary & {
  saved_papers: Paper[]
  searches: SearchHistory[]
}

const API_URL = import.meta.env.VITE_API_URL ?? 'http://localhost:3000'

const sourceOptions: Array<{ key: SourceKey; label: string }> = [
  { key: 'semantic_scholar', label: 'Semantic Scholar' },
  { key: 'openalex', label: 'OpenAlex' },
  { key: 'crossref', label: 'Crossref' },
  { key: 'pubmed', label: 'PubMed' },
  { key: 'arxiv', label: 'arXiv' },
]

const paperKey = (paper: Paper) => `${paper.source}::${paper.external_id}`

async function requestJson<T>(path: string, init?: RequestInit): Promise<T> {
  const response = await fetch(`${API_URL}${path}`, {
    headers: {
      'Content-Type': 'application/json',
      ...(init?.headers ?? {}),
    },
    ...init,
  })

  if (!response.ok) {
    const message = await response.text()
    throw new Error(message || `Request failed with status ${response.status}`)
  }

  return response.json() as Promise<T>
}

function App() {
  const [isSidebarCollapsed, setIsSidebarCollapsed] = useState(false)
  const [workspaces, setWorkspaces] = useState<WorkspaceSummary[]>([])
  const [activeWorkspaceId, setActiveWorkspaceId] = useState<number | null>(null)
  const [workspaceDetail, setWorkspaceDetail] = useState<WorkspaceDetail | null>(null)
  const [query, setQuery] = useState('')
  const [enabledSources, setEnabledSources] = useState<SourceKey[]>(sourceOptions.map((option) => option.key))
  const [showAdvancedSearch, setShowAdvancedSearch] = useState(false)
  const [yearFrom, setYearFrom] = useState('')
  const [yearTo, setYearTo] = useState('')
  const [limitPerSource, setLimitPerSource] = useState('4')
  const [openAccessOnly, setOpenAccessOnly] = useState(false)
  const [sortBy, setSortBy] = useState<SortOption>('relevance')
  const [searchResults, setSearchResults] = useState<Paper[]>([])
  const [sourceErrors, setSourceErrors] = useState<Record<string, string>>({})
  const [selectedPaperKeys, setSelectedPaperKeys] = useState<string[]>([])
  const [synthesisQuestion, setSynthesisQuestion] = useState('')
  const [readingObjective, setReadingObjective] = useState('')
  const [synthesisOutput, setSynthesisOutput] = useState('')
  const [readingPath, setReadingPath] = useState<ReadingPathResponse | null>(null)
  const [isSearching, setIsSearching] = useState(false)
  const [isSynthesizing, setIsSynthesizing] = useState(false)
  const [isBuildingReadingPath, setIsBuildingReadingPath] = useState(false)
  const [isSavingNotes, setIsSavingNotes] = useState(false)
  const [isExporting, setIsExporting] = useState(false)
  const [notesDraft, setNotesDraft] = useState('')
  const [error, setError] = useState('')
  const [editingWorkspaceId, setEditingWorkspaceId] = useState<number | null>(null)
  const [workspaceTitleDraft, setWorkspaceTitleDraft] = useState('')

  const activeWorkspace = useMemo(
    () => workspaces.find((workspace) => workspace.id === activeWorkspaceId) ?? null,
    [activeWorkspaceId, workspaces],
  )

  const allVisiblePapers = useMemo(() => {
    const merged = new Map<string, Paper>()
    for (const paper of workspaceDetail?.saved_papers ?? []) {
      merged.set(paperKey(paper), paper)
    }
    for (const paper of searchResults) {
      merged.set(paperKey(paper), paper)
    }
    return merged
  }, [searchResults, workspaceDetail?.saved_papers])

  const selectedPapers = useMemo(
    () => selectedPaperKeys.map((key) => allVisiblePapers.get(key)).filter(Boolean) as Paper[],
    [allVisiblePapers, selectedPaperKeys],
  )

  const savedPaperKeys = useMemo(
    () => new Set((workspaceDetail?.saved_papers ?? []).map((paper) => paperKey(paper))),
    [workspaceDetail?.saved_papers],
  )

  useEffect(() => {
    void loadWorkspaces()
  }, [])

  useEffect(() => {
    if (activeWorkspaceId !== null) {
      void loadWorkspaceDetail(activeWorkspaceId)
    }
  }, [activeWorkspaceId])

  useEffect(() => {
    setNotesDraft(workspaceDetail?.notes ?? '')
  }, [workspaceDetail?.notes, workspaceDetail?.id])

  async function loadWorkspaces(nextActiveWorkspaceId?: number) {
    try {
      const data = await requestJson<WorkspaceSummary[]>('/api/workspaces/')
      setWorkspaces(data)

      if (data.length === 0) {
        const created = await requestJson<WorkspaceDetail>('/api/workspaces/', {
          method: 'POST',
          body: JSON.stringify({ title: 'New workspace' }),
        })
        setWorkspaces([created])
        setActiveWorkspaceId(created.id)
        setWorkspaceDetail(created)
        return
      }

      const targetId =
        nextActiveWorkspaceId ??
        (activeWorkspaceId !== null && data.some((workspace) => workspace.id === activeWorkspaceId)
          ? activeWorkspaceId
          : data[0].id)
      setActiveWorkspaceId(targetId)
    } catch (caught) {
      setError(caught instanceof Error ? caught.message : 'Failed to load workspaces.')
    }
  }

  async function loadWorkspaceDetail(workspaceId: number) {
    try {
      const data = await requestJson<WorkspaceDetail>(`/api/workspaces/${workspaceId}`)
      setWorkspaceDetail(data)
    } catch (caught) {
      setError(caught instanceof Error ? caught.message : 'Failed to load workspace detail.')
    }
  }

  async function createWorkspace() {
    try {
      const created = await requestJson<WorkspaceDetail>('/api/workspaces/', {
        method: 'POST',
        body: JSON.stringify({ title: 'New workspace' }),
      })
      setError('')
      setEditingWorkspaceId(created.id)
      setWorkspaceTitleDraft('')
      setIsSidebarCollapsed(false)
      await loadWorkspaces(created.id)
    } catch (caught) {
      setError(caught instanceof Error ? caught.message : 'Failed to create workspace.')
    }
  }

  async function deleteWorkspace(workspaceId: number) {
    try {
      await requestJson(`/api/workspaces/${workspaceId}`, { method: 'DELETE' })
      setSearchResults([])
      setSelectedPaperKeys([])
      setSynthesisOutput('')
      await loadWorkspaces()
    } catch (caught) {
      setError(caught instanceof Error ? caught.message : 'Failed to delete workspace.')
    }
  }

  async function renameWorkspace(workspaceId: number) {
    const nextTitle = workspaceTitleDraft.trim() || 'New workspace'
    try {
      await requestJson<WorkspaceSummary>(`/api/workspaces/${workspaceId}`, {
        method: 'PATCH',
        body: JSON.stringify({ title: nextTitle }),
      })
      setEditingWorkspaceId(null)
      setWorkspaceTitleDraft('')
      await loadWorkspaces(workspaceId)
    } catch (caught) {
      setError(caught instanceof Error ? caught.message : 'Failed to rename workspace.')
    }
  }

  async function saveNotes() {
    if (!workspaceDetail) return
    setIsSavingNotes(true)
    try {
      const updated = await requestJson<WorkspaceSummary>(`/api/workspaces/${workspaceDetail.id}`, {
        method: 'PATCH',
        body: JSON.stringify({ notes: notesDraft }),
      })
      setWorkspaceDetail((current) => (current ? { ...current, notes: updated.notes, updated_at: updated.updated_at } : current))
      setWorkspaces((current) =>
        current.map((workspace) => (workspace.id === updated.id ? updated : workspace)),
      )
    } catch (caught) {
      setError(caught instanceof Error ? caught.message : 'Failed to save notes.')
    } finally {
      setIsSavingNotes(false)
    }
  }

  async function onSearch(event?: FormEvent, nextQuery?: string) {
    event?.preventDefault()
    const effectiveQuery = (nextQuery ?? query).trim()
    if (!effectiveQuery || activeWorkspaceId === null || enabledSources.length === 0) return

    setIsSearching(true)
    setError('')
    setSourceErrors({})
    setSynthesisOutput('')
    setReadingPath(null)

    try {
      const payload = {
        query: effectiveQuery,
        limit_per_source: Number(limitPerSource) || 4,
        sources: enabledSources,
        workspace_id: activeWorkspaceId,
        year_from: yearFrom ? Number(yearFrom) : null,
        year_to: yearTo ? Number(yearTo) : null,
        open_access_only: openAccessOnly,
        sort_by: sortBy,
      }
      const response = await requestJson<SearchResponse>('/api/research/search', {
        method: 'POST',
        body: JSON.stringify(payload),
      })
      setQuery(effectiveQuery)
      setSearchResults(response.results)
      setSourceErrors(response.source_errors ?? {})
      setSelectedPaperKeys([])
      await loadWorkspaceDetail(activeWorkspaceId)
      await loadWorkspaces(activeWorkspaceId)
    } catch (caught) {
      setError(caught instanceof Error ? caught.message : 'Search failed.')
    } finally {
      setIsSearching(false)
    }
  }

  async function savePaperToWorkspace(paper: Paper) {
    if (!workspaceDetail) return
    try {
      await requestJson(`/api/workspaces/${workspaceDetail.id}/papers`, {
        method: 'POST',
        body: JSON.stringify(paper),
      })
      await loadWorkspaceDetail(workspaceDetail.id)
      await loadWorkspaces(workspaceDetail.id)
    } catch (caught) {
      setError(caught instanceof Error ? caught.message : 'Failed to save paper.')
    }
  }

  async function removePaperFromWorkspace(paper: Paper) {
    if (!workspaceDetail) return
    try {
      await requestJson(
        `/api/workspaces/${workspaceDetail.id}/papers/${encodeURIComponent(paper.source)}/${encodeURIComponent(paper.external_id)}`,
        { method: 'DELETE' },
      )
      setSelectedPaperKeys((current) => current.filter((key) => key !== paperKey(paper)))
      await loadWorkspaceDetail(workspaceDetail.id)
      await loadWorkspaces(workspaceDetail.id)
    } catch (caught) {
      setError(caught instanceof Error ? caught.message : 'Failed to remove paper.')
    }
  }

  async function runSynthesis(mode: 'summary' | 'compare' | 'question') {
    if (selectedPapers.length === 0) {
      setError('Select at least one paper first.')
      return
    }

    if (mode === 'compare' && selectedPapers.length < 2) {
      setError('Select at least two papers to compare.')
      return
    }

    if (mode === 'question' && !synthesisQuestion.trim()) {
      setError('Enter a question for the selected papers.')
      return
    }

    setIsSynthesizing(true)
    setError('')

    try {
      const response = await requestJson<{ response: string }>('/api/research/synthesize', {
        method: 'POST',
        body: JSON.stringify({
          mode,
          question: mode === 'question' ? synthesisQuestion.trim() : null,
          papers: selectedPapers,
        }),
      })
      setSynthesisOutput(response.response)
      setReadingPath(null)
    } catch (caught) {
      setError(caught instanceof Error ? caught.message : 'Failed to synthesize papers.')
    } finally {
      setIsSynthesizing(false)
    }
  }

  async function buildReadingPath() {
    if (selectedPapers.length === 0) {
      setError('Select at least one paper first.')
      return
    }

    setIsBuildingReadingPath(true)
    setError('')

    try {
      const response = await requestJson<ReadingPathResponse>('/api/research/reading-path', {
        method: 'POST',
        body: JSON.stringify({
          objective: readingObjective.trim() || null,
          papers: selectedPapers,
        }),
      })
      setReadingPath(response)
      setSynthesisOutput('')
    } catch (caught) {
      setError(caught instanceof Error ? caught.message : 'Failed to build reading path.')
    } finally {
      setIsBuildingReadingPath(false)
    }
  }

  async function exportSelectedPapers(format: 'bibtex' | 'markdown') {
    if (selectedPapers.length === 0) {
      setError('Select at least one paper to export.')
      return
    }

    setIsExporting(true)
    setError('')

    try {
      const response = await requestJson<ExportResponse>('/api/research/export', {
        method: 'POST',
        body: JSON.stringify({
          format,
          papers: selectedPapers,
        }),
      })
      await navigator.clipboard.writeText(response.content)
      setSynthesisOutput(
        `${format === 'bibtex' ? 'BibTeX' : 'Markdown'} export copied to your clipboard for ${selectedPapers.length} selected papers.`,
      )
    } catch (caught) {
      setError(caught instanceof Error ? caught.message : 'Failed to export papers.')
    } finally {
      setIsExporting(false)
    }
  }

  function toggleSource(source: SourceKey) {
    setEnabledSources((current) =>
      current.includes(source) ? current.filter((item) => item !== source) : [...current, source],
    )
  }

  function togglePaperSelection(paper: Paper) {
    const key = paperKey(paper)
    setSelectedPaperKeys((current) =>
      current.includes(key) ? current.filter((item) => item !== key) : [...current, key],
    )
  }

  function handleNotesChange(event: ChangeEvent<HTMLTextAreaElement>) {
    setNotesDraft(event.target.value)
  }

  const isBootstrapping = workspaces.length === 0 && activeWorkspaceId === null && !error

  return (
    <main className={`app-shell${isSidebarCollapsed ? ' sidebar-collapsed' : ''}`}>
      <aside className={`sidebar${isSidebarCollapsed ? ' collapsed' : ''}`}>
        <div className="sidebar-top">
          <div className="sidebar-brand">
            <div>
              <p className="eyebrow">{isSidebarCollapsed ? 'RCA' : 'Research Companion Agent'}</p>
              {!isSidebarCollapsed && <h1>Research desk</h1>}
              {!isSidebarCollapsed && (
                <p className="intro">
                  Search publications, keep the strongest papers close, and turn a loose topic into a readable path.
                </p>
              )}
            </div>
            <button
              aria-label={isSidebarCollapsed ? 'Expand sidebar' : 'Collapse sidebar'}
              className="sidebar-toggle"
              type="button"
              onClick={() => setIsSidebarCollapsed((current) => !current)}
            >
              {isSidebarCollapsed ? '>' : '<'}
            </button>
          </div>

          <section className="workspace-panel">
            <div className="section-header">
              {!isSidebarCollapsed && <p className="panel-label">Workspaces</p>}
              <button
                className={`secondary-button${isSidebarCollapsed ? ' icon-button' : ''}`}
                title="Create workspace"
                type="button"
                onClick={createWorkspace}
              >
                {isSidebarCollapsed ? '+' : 'New'}
              </button>
            </div>

            {!isSidebarCollapsed && (
              <div className="workspace-list">
                {isBootstrapping ? (
                  <article className="workspace-card active">
                    <h2>Loading workspace...</h2>
                    <p>Preparing your research desk.</p>
                  </article>
                ) : (
                  workspaces.map((workspace) => (
                    <article
                      key={workspace.id}
                      className={`workspace-card${workspace.id === activeWorkspaceId ? ' active' : ''}`}
                      title={workspace.title}
                      onClick={() => setActiveWorkspaceId(workspace.id)}
                    >
                      {editingWorkspaceId === workspace.id ? (
                        <input
                          autoFocus
                          className="workspace-input"
                          onBlur={() => void renameWorkspace(workspace.id)}
                          onChange={(event) => setWorkspaceTitleDraft(event.target.value)}
                          onKeyDown={(event) => {
                            if (event.key === 'Enter') {
                              event.preventDefault()
                              void renameWorkspace(workspace.id)
                            }
                          if (event.key === 'Escape') {
                            setEditingWorkspaceId(null)
                            setWorkspaceTitleDraft('')
                          }
                        }}
                          placeholder="Name this workspace"
                          value={workspaceTitleDraft}
                        />
                      ) : (
                        <h2>{workspace.title}</h2>
                      )}
                      <p>{workspace.saved_paper_count} saved papers</p>
                      <div className="workspace-actions">
                        <button
                          type="button"
                          onClick={(event) => {
                            event.stopPropagation()
                            setEditingWorkspaceId(workspace.id)
                            setWorkspaceTitleDraft(workspace.title)
                          }}
                        >
                          Rename
                        </button>
                        <button
                          type="button"
                          onClick={(event) => {
                            event.stopPropagation()
                            void deleteWorkspace(workspace.id)
                          }}
                        >
                          Delete
                        </button>
                      </div>
                    </article>
                  ))
                )}
              </div>
            )}
          </section>

        </div>

        <div className="status-panel">
          <span className="status-dot" />
          {!isSidebarCollapsed && <span>{isSearching || isSynthesizing ? 'Working through sources' : 'Ready to search'}</span>}
        </div>
      </aside>

      <section className="main-panel">
        <section className="search-panel">
          <div className="section-header">
            <div>
              <p className="panel-label">Search</p>
              <h2 className="section-title">{activeWorkspace?.title ?? 'Loading workspace...'}</h2>
            </div>
            <p className="section-kicker">Cross-source literature search</p>
          </div>

          <form className="search-form" onSubmit={(event) => void onSearch(event)}>
            <input
              aria-label="Search research publications"
              className="search-input"
              onChange={(event) => setQuery(event.target.value)}
              placeholder="Search for a topic, method, benchmark, or paper family"
              value={query}
            />
            <div className="action-row">
              <button className="primary-button" disabled={isSearching || !query.trim() || enabledSources.length === 0} type="submit">
                {isSearching ? 'Searching' : 'Search publications'}
              </button>
              <button
                className="ghost-button"
                type="button"
                onClick={() => setShowAdvancedSearch((current) => !current)}
              >
                {showAdvancedSearch ? 'Hide advanced search' : 'Advanced search'}
              </button>
            </div>
            <div className="source-row">
              {sourceOptions.map((option) => (
                <label className={`source-chip${enabledSources.includes(option.key) ? ' active' : ''}`} key={option.key}>
                  <input
                    checked={enabledSources.includes(option.key)}
                    onChange={() => toggleSource(option.key)}
                    type="checkbox"
                  />
                  <span>{option.label}</span>
                </label>
              ))}
            </div>
            {showAdvancedSearch && (
              <section className="advanced-search-panel">
                <div className="advanced-grid">
                  <label className="field">
                    <span>Year from</span>
                    <input value={yearFrom} onChange={(event) => setYearFrom(event.target.value)} placeholder="2019" />
                  </label>
                  <label className="field">
                    <span>Year to</span>
                    <input value={yearTo} onChange={(event) => setYearTo(event.target.value)} placeholder="2026" />
                  </label>
                  <label className="field">
                    <span>Results per source</span>
                    <select value={limitPerSource} onChange={(event) => setLimitPerSource(event.target.value)}>
                      <option value="3">3</option>
                      <option value="4">4</option>
                      <option value="5">5</option>
                      <option value="7">7</option>
                      <option value="10">10</option>
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
                </div>
                <label className="toggle-row">
                  <input checked={openAccessOnly} onChange={(event) => setOpenAccessOnly(event.target.checked)} type="checkbox" />
                  <span>Open access only</span>
                </label>
              </section>
            )}
          </form>

          {Object.keys(sourceErrors ?? {}).length > 0 && (
            <div className="error-box">
              {Object.entries(sourceErrors ?? {}).map(([source, message]) => (
                <p key={source}>
                  <strong>{source}:</strong> {message}
                </p>
              ))}
            </div>
          )}
        </section>

        <section className="content-grid">
          <div className="results-panel">
            <div className="section-header">
              <p className="panel-label">Results</p>
              <span className="panel-meta">{searchResults.length} papers</span>
            </div>
            <div className="card-list">
              {searchResults.length === 0 ? (
                <article className="empty-card">
                  <p className="empty-card-title">No papers yet</p>
                  <p className="empty-state">
                    Run a search to pull in papers from the sources you selected. This column becomes your working stack.
                  </p>
                </article>
              ) : (
                searchResults.map((paper) => {
                  const key = paperKey(paper)
                  const isSelected = selectedPaperKeys.includes(key)
                  const isSaved = savedPaperKeys.has(key)

                  return (
                    <article className={`paper-card${isSelected ? ' selected' : ''}`} key={key}>
                      <div className="paper-card-header">
                        <label className="checkbox-row">
                          <input checked={isSelected} onChange={() => togglePaperSelection(paper)} type="checkbox" />
                          <span>Select</span>
                        </label>
                        <span className="source-tag">{paper.source}</span>
                      </div>
                      <h3>{paper.title}</h3>
                      <p className="paper-meta">
                        {paper.authors.slice(0, 4).join(', ') || 'Unknown authors'}
                        {paper.year ? ` · ${paper.year}` : ''}
                        {paper.venue ? ` · ${paper.venue}` : ''}
                      </p>
                      <div className="paper-badges">
                        {paper.citation_count !== null && <span className="paper-badge">{paper.citation_count} citations</span>}
                        {paper.open_access && <span className="paper-badge">Open access</span>}
                        {paper.doi && <span className="paper-badge">DOI</span>}
                      </div>
                      <p className="paper-abstract">{paper.abstract || 'No abstract available.'}</p>
                      <div className="paper-actions">
                        <button type="button" onClick={() => void savePaperToWorkspace(paper)} disabled={isSaved}>
                          {isSaved ? 'Saved' : 'Save'}
                        </button>
                        {paper.url && (
                          <a href={paper.url} rel="noreferrer" target="_blank">
                            Open
                          </a>
                        )}
                        {paper.pdf_url && (
                          <a href={paper.pdf_url} rel="noreferrer" target="_blank">
                            PDF
                          </a>
                        )}
                      </div>
                    </article>
                  )
                })
              )}
            </div>
          </div>

          <aside className="workspace-detail-panel">
            <section className="detail-section selected-tray">
              <div className="section-header">
                <p className="panel-label">Selected papers</p>
                <span className="panel-meta">{selectedPapers.length}</span>
              </div>
              <div className="selected-chip-list">
                {selectedPapers.length > 0 ? (
                  selectedPapers.map((paper) => (
                    <button
                      key={paperKey(paper)}
                      className="selected-chip"
                      type="button"
                      onClick={() => togglePaperSelection(paper)}
                    >
                      <span>{paper.title}</span>
                      <strong>Remove</strong>
                    </button>
                  ))
                ) : (
                  <p className="empty-state">Select papers from results or your saved list to synthesize or export them.</p>
                )}
              </div>
              <div className="synthesis-actions">
                <button className="secondary-button" disabled={isExporting || selectedPapers.length === 0} type="button" onClick={() => void exportSelectedPapers('bibtex')}>
                  {isExporting ? 'Exporting' : 'Copy BibTeX'}
                </button>
                <button className="secondary-button" disabled={isExporting || selectedPapers.length === 0} type="button" onClick={() => void exportSelectedPapers('markdown')}>
                  {isExporting ? 'Exporting' : 'Copy Reading List'}
                </button>
              </div>
            </section>

            <section className="detail-section">
              <div className="section-header">
                <p className="panel-label">Saved papers</p>
                <span className="panel-meta">{workspaceDetail?.saved_papers?.length ?? 0}</span>
              </div>
              <div className="card-list compact">
                {(workspaceDetail?.saved_papers ?? []).length === 0 ? (
                  <p className="empty-state">Saved papers will appear here once you pin strong results into this workspace.</p>
                ) : (
                  (workspaceDetail?.saved_papers ?? []).map((paper) => {
                    const key = paperKey(paper)
                    return (
                      <article className={`paper-card compact${selectedPaperKeys.includes(key) ? ' selected' : ''}`} key={key}>
                        <div className="paper-card-header">
                          <label className="checkbox-row">
                            <input checked={selectedPaperKeys.includes(key)} onChange={() => togglePaperSelection(paper)} type="checkbox" />
                            <span>Select</span>
                          </label>
                          <span className="source-tag">{paper.source}</span>
                        </div>
                        <h3>{paper.title}</h3>
                        <p className="paper-meta">{paper.year ? `${paper.year}` : 'Year unknown'}{paper.venue ? ` · ${paper.venue}` : ''}</p>
                        <div className="paper-actions">
                          <button type="button" onClick={() => void removePaperFromWorkspace(paper)}>
                            Remove
                          </button>
                          {paper.url && (
                            <a href={paper.url} rel="noreferrer" target="_blank">
                              Open
                            </a>
                          )}
                        </div>
                      </article>
                    )
                  })
                )}
              </div>
            </section>

            <section className="detail-section">
              <div className="section-header">
                <p className="panel-label">Synthesis</p>
                <span className="panel-meta">{selectedPapers.length} selected</span>
              </div>
              <textarea
                className="question-input"
                onChange={(event) => setReadingObjective(event.target.value)}
                placeholder="Optional reading goal, like learn the basics fast or compare evaluation methods..."
                rows={2}
                value={readingObjective}
              />
              <div className="synthesis-actions">
                <button className="secondary-button" disabled={isBuildingReadingPath || selectedPapers.length === 0} type="button" onClick={() => void buildReadingPath()}>
                  {isBuildingReadingPath ? 'Planning' : 'Build reading path'}
                </button>
              </div>
              <textarea
                className="question-input"
                onChange={(event) => setSynthesisQuestion(event.target.value)}
                placeholder="Ask a question across the selected papers..."
                rows={3}
                value={synthesisQuestion}
              />
              <div className="synthesis-actions">
                <button className="primary-button" disabled={isSynthesizing || selectedPapers.length === 0} type="button" onClick={() => void runSynthesis('summary')}>
                  Summarize
                </button>
                <button className="secondary-button" disabled={isSynthesizing || selectedPapers.length < 2} type="button" onClick={() => void runSynthesis('compare')}>
                  Compare
                </button>
                <button className="secondary-button" disabled={isSynthesizing || !synthesisQuestion.trim() || selectedPapers.length === 0} type="button" onClick={() => void runSynthesis('question')}>
                  Ask
                </button>
              </div>
              <div className="synthesis-output">
                {readingPath ? (
                  <div className="reading-path">
                    <p className="reading-path-overview"><strong>{readingPath.objective}</strong></p>
                    <p className="reading-path-overview">{readingPath.overview}</p>
                    <div className="reading-path-list">
                      {readingPath.steps.map((step) => (
                        <article className="reading-step" key={`${step.source}-${step.external_id}-${step.order}`}>
                          <span className="reading-step-order">{step.order}</span>
                          <div>
                            <h4>{step.title}</h4>
                            <p className="paper-meta">{step.source}</p>
                            <p>{step.rationale}</p>
                          </div>
                        </article>
                      ))}
                    </div>
                  </div>
                ) : (
                  <p>{synthesisOutput || 'Select papers and run a synthesis to generate a working brief.'}</p>
                )}
              </div>
            </section>

            <section className="detail-section">
              <div className="section-header">
                <p className="panel-label">Notes</p>
                <button className="secondary-button" disabled={isSavingNotes || workspaceDetail === null} type="button" onClick={() => void saveNotes()}>
                  {isSavingNotes ? 'Saving' : 'Save notes'}
                </button>
              </div>
              <textarea className="notes-input" onChange={handleNotesChange} placeholder="Capture takeaways, hypotheses, and next reads..." rows={8} value={notesDraft} />
            </section>

            <section className="detail-section">
              <div className="section-header">
                <p className="panel-label">Recent searches</p>
              </div>
              <div className="history-list">
                {(workspaceDetail?.searches ?? []).length === 0 ? (
                  <p className="empty-state">Search history will collect here as you explore this workspace.</p>
                ) : (
                  (workspaceDetail?.searches ?? []).slice(0, 8).map((search) => (
                    <button
                      key={search.id}
                      className="history-card"
                      type="button"
                      onClick={() => {
                        setQuery(search.query)
                        setEnabledSources(
                          sourceOptions
                            .map((option) => option.key)
                            .filter((source): source is SourceKey => search.sources.includes(source)),
                        )
                      }}
                    >
                      <strong>{search.query}</strong>
                      <span>
                        {search.result_count} results · {search.sources.join(', ')}
                      </span>
                    </button>
                  ))
                )}
              </div>
            </section>
          </aside>
        </section>

        {error && <p className="global-error">{error}</p>}
      </section>
    </main>
  )
}

export default App
