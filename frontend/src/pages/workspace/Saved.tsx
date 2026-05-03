import { useEffect, useMemo, useState } from 'react'
import { Link, useParams } from 'react-router-dom'
import { paperKey, type SourceKey } from '../../api/types'
import { EmptyState } from '../../components/EmptyState'
import { PaperCard } from '../../components/PaperCard'
import { SOURCE_OPTIONS } from '../../api/types'
import { useWorkspaceStore } from '../../state/WorkspaceStore'

type SortKey = 'recent' | 'newest' | 'most_cited' | 'title'

export function SavedTab() {
  const { workspaceId } = useParams<{ workspaceId: string }>()
  const id = Number(workspaceId)
  const {
    workspaceDetails,
    refreshWorkspace,
    removePaper,
    updatePaperNote,
    togglePaperSelection,
    isSelected,
    setSelection,
    selection,
  } = useWorkspaceStore()
  const detail = workspaceDetails[id]

  const [sourceFilter, setSourceFilter] = useState<SourceKey | 'all'>('all')
  const [sort, setSort] = useState<SortKey>('recent')
  const [yearFilter, setYearFilter] = useState<'all' | 'recent5' | 'recent10'>('all')
  const [detailReady, setDetailReady] = useState(false)

  useEffect(() => {
    if (Number.isNaN(id)) {
      setDetailReady(true)
      return
    }
    setDetailReady(false)
    void refreshWorkspace(id).finally(() => setDetailReady(true))
  }, [id, refreshWorkspace])

  const papers = useMemo(() => {
    const all = detail?.saved_papers ?? []
    let filtered = all
    if (sourceFilter !== 'all') filtered = filtered.filter((paper) => paper.source === sourceFilter)
    if (yearFilter === 'recent5' || yearFilter === 'recent10') {
      const horizon = new Date().getFullYear() - (yearFilter === 'recent5' ? 5 : 10)
      filtered = filtered.filter((paper) => paper.year != null && paper.year >= horizon)
    }
    const sorted = [...filtered]
    if (sort === 'newest') {
      sorted.sort((a, b) => (b.year ?? -Infinity) - (a.year ?? -Infinity))
    } else if (sort === 'most_cited') {
      sorted.sort((a, b) => (b.citation_count ?? -1) - (a.citation_count ?? -1))
    } else if (sort === 'title') {
      sorted.sort((a, b) => a.title.localeCompare(b.title))
    }
    return sorted
  }, [detail?.saved_papers, sort, sourceFilter, yearFilter])

  const allKeys = useMemo(() => papers.map((paper) => paperKey(paper)), [papers])
  const allSelected = allKeys.length > 0 && allKeys.every((key) => selection.papers.some((paper) => paperKey(paper) === key))

  const savedTotal = detail?.saved_papers?.length ?? 0
  const libraryEmpty = detailReady && savedTotal === 0
  const noteByPaper = useMemo(() => {
    const map = new Map<string, string>()
    for (const note of detail?.paper_notes ?? []) {
      map.set(`${note.source}::${note.external_id}`, note.note)
    }
    return map
  }, [detail?.paper_notes])

  if (!detailReady) {
    return (
      <div className="saved-tab">
        <p className="muted">Loading saved papers…</p>
      </div>
    )
  }

  return (
    <div className="saved-tab">
      <section className="surface saved-controls">
        <div className="filter-row">
          <label className="field-inline">
            <span>Source</span>
            <select value={sourceFilter} onChange={(event) => setSourceFilter(event.target.value as SourceKey | 'all')}>
              <option value="all">All sources</option>
              {SOURCE_OPTIONS.map((option) => (
                <option key={option.key} value={option.key}>
                  {option.label}
                </option>
              ))}
            </select>
          </label>
          <label className="field-inline">
            <span>Recency</span>
            <select value={yearFilter} onChange={(event) => setYearFilter(event.target.value as 'all' | 'recent5' | 'recent10')}>
              <option value="all">All years</option>
              <option value="recent5">Last 5 years</option>
              <option value="recent10">Last 10 years</option>
            </select>
          </label>
          <label className="field-inline">
            <span>Sort</span>
            <select value={sort} onChange={(event) => setSort(event.target.value as SortKey)}>
              <option value="recent">Recently added</option>
              <option value="newest">Newest publication</option>
              <option value="most_cited">Most cited</option>
              <option value="title">Title (A → Z)</option>
            </select>
          </label>
          <div className="filter-row-end">
            <button
              type="button"
              className="link-button"
              disabled={papers.length === 0}
              onClick={() => {
                if (allSelected) {
                  setSelection(id, [])
                } else {
                  setSelection(id, papers)
                }
              }}
            >
              {allSelected ? 'Clear selection' : `Select all (${papers.length})`}
            </button>
            <Link className="pill-button is-ghost" to={`/workspaces/${id}/synthesis`}>
              Open synthesis
            </Link>
          </div>
        </div>
      </section>

      {papers.length === 0 ? (
        <EmptyState
          size="lg"
          icon={libraryEmpty ? '📚' : '🔍'}
          title={libraryEmpty ? 'Your library is empty' : 'No papers match these filters'}
          description={
            libraryEmpty
              ? 'Save papers from the Search tab and they will collect here.'
              : 'Try clearing a filter, or run a new search.'
          }
          action={
            libraryEmpty ? (
              <Link className="pill-button is-primary" to={`/workspaces/${id}/search`}>
                Open search
              </Link>
            ) : (
              <button
                className="pill-button is-ghost"
                type="button"
                onClick={() => {
                  setSourceFilter('all')
                  setYearFilter('all')
                }}
              >
                Reset filters
              </button>
            )
          }
        />
      ) : (
        <div className="card-list">
          {papers.map((paper) => (
            <PaperCard
              key={paperKey(paper)}
              paper={paper}
              isSelected={isSelected(paper)}
              isSaved
              note={noteByPaper.get(paperKey(paper)) ?? ''}
              onToggleSelect={(item) => togglePaperSelection(id, item)}
              onRemove={(item) => void removePaper(id, item)}
              onSaveNote={(item, note) => void updatePaperNote(id, item, note)}
            />
          ))}
        </div>
      )}
    </div>
  )
}
