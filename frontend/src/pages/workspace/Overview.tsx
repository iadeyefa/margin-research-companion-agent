import { useMemo } from 'react'
import { Link, useParams } from 'react-router-dom'
import { EmptyState } from '../../components/EmptyState'
import { PageLoading } from '../../components/PageLoading'
import { SourceTag } from '../../components/SourceTag'
import { useWorkspaceStore } from '../../state/WorkspaceStore'

function formatRelative(value: string): string {
  const date = new Date(value)
  if (Number.isNaN(date.getTime())) return value
  const minutes = Math.round((Date.now() - date.getTime()) / 60000)
  if (minutes < 1) return 'just now'
  if (minutes < 60) return `${minutes}m ago`
  const hours = Math.round(minutes / 60)
  if (hours < 24) return `${hours}h ago`
  const days = Math.round(hours / 24)
  return `${days}d ago`
}

export function OverviewTab() {
  const { workspaceId } = useParams<{ workspaceId: string }>()
  const id = Number(workspaceId)
  const { workspaceDetails } = useWorkspaceStore()
  const detail = workspaceDetails[id]

  const themeChips = useMemo(() => {
    if (!detail) return []
    const counts = new Map<string, number>()
    for (const paper of detail.saved_papers) {
      const tokens = paper.title
        .toLowerCase()
        .replace(/[^a-z0-9 ]/g, ' ')
        .split(/\s+/)
        .filter((token) => token.length > 4)
      const seen = new Set<string>()
      for (const token of tokens) {
        if (seen.has(token)) continue
        seen.add(token)
        counts.set(token, (counts.get(token) ?? 0) + 1)
      }
    }
    return Array.from(counts.entries())
      .filter(([, count]) => count >= 2)
      .sort((a, b) => b[1] - a[1])
      .slice(0, 8)
      .map(([token]) => token)
  }, [detail])

  if (!detail) {
    return <PageLoading message="Loading workspace overview…" />
  }

  const recentSearches = detail.searches.slice(0, 4)
  const recentPapers = detail.saved_papers.slice(0, 5)
  const briefsForWorkspace = detail.briefs ?? []
  const firstNoteLine = detail.notes.split('\n').find((line) => line.trim().length > 0) ?? ''

  return (
    <div className="overview-grid">
      <section className="surface">
        <p className="surface-eyebrow">Snapshot</p>
        <div className="overview-stats">
          <div>
            <p className="overview-stat-value">{detail.saved_paper_count}</p>
            <p className="overview-stat-label">Saved papers</p>
          </div>
          <div>
            <p className="overview-stat-value">{detail.search_count}</p>
            <p className="overview-stat-label">Searches</p>
          </div>
          <div>
            <p className="overview-stat-value">{briefsForWorkspace.length}</p>
            <p className="overview-stat-label">Briefs</p>
          </div>
          <div>
            <p className="overview-stat-value">{formatRelative(detail.updated_at)}</p>
            <p className="overview-stat-label">Last updated</p>
          </div>
        </div>
        <div className="overview-themes">
          <p className="overview-section-label">Major themes</p>
          {themeChips.length === 0 ? (
            <p className="muted">Save more papers to surface common themes.</p>
          ) : (
            <div className="theme-chip-row">
              {themeChips.map((token) => (
                <span key={token} className="theme-chip">
                  {token}
                </span>
              ))}
            </div>
          )}
        </div>
      </section>

      <section className="surface">
        <div className="surface-header">
          <p className="surface-eyebrow">Recent reads</p>
          <Link className="link-button" to={`/workspaces/${id}/saved`}>
            View saved
          </Link>
        </div>
        {recentPapers.length === 0 ? (
          <EmptyState
            title="No papers saved yet"
            description="Use the Search tab to find papers and save them here."
            action={
              <Link className="pill-button is-primary" to={`/workspaces/${id}/search`}>
                Search papers
              </Link>
            }
          />
        ) : (
          <ul className="dashboard-list">
            {recentPapers.map((paper) => (
              <li key={`${paper.source}-${paper.external_id}`}>
                <Link
                  to={`/papers/${encodeURIComponent(paper.source)}/${encodeURIComponent(paper.external_id)}`}
                  state={{ paper }}
                  className="dashboard-list-row"
                >
                  <SourceTag source={paper.source} />
                  <div className="dashboard-list-body">
                    <p className="dashboard-list-title">{paper.title}</p>
                    <p className="dashboard-list-meta">
                      {paper.year ?? 'Year unknown'} · {paper.authors.slice(0, 3).join(', ') || 'Unknown authors'}
                    </p>
                  </div>
                </Link>
              </li>
            ))}
          </ul>
        )}
      </section>

      <section className="surface">
        <div className="surface-header">
          <p className="surface-eyebrow">Open questions</p>
          <Link className="link-button" to={`/workspaces/${id}/notes`}>
            Edit notes
          </Link>
        </div>
        {firstNoteLine ? (
          <p className="overview-note-preview">{firstNoteLine}</p>
        ) : (
          <EmptyState title="No notes" description="Capture takeaways, hypotheses, and follow-ups." />
        )}
      </section>

      <section className="surface">
        <div className="surface-header">
          <p className="surface-eyebrow">Activity</p>
          <Link className="link-button" to={`/workspaces/${id}/history`}>
            History
          </Link>
        </div>
        {recentSearches.length === 0 ? (
          <EmptyState title="No searches yet" description="Searches you run in this workspace appear here." />
        ) : (
          <ul className="dashboard-list">
            {recentSearches.map((search) => (
              <li key={search.id}>
                <Link to={`/workspaces/${id}/search`} className="dashboard-list-row">
                  <span className="dashboard-list-icon">🔎</span>
                  <div className="dashboard-list-body">
                    <p className="dashboard-list-title">{search.query}</p>
                    <p className="dashboard-list-meta">
                      {search.result_count} results · {formatRelative(search.created_at)}
                    </p>
                  </div>
                </Link>
              </li>
            ))}
          </ul>
        )}
      </section>
    </div>
  )
}
