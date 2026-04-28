import { useParams } from 'react-router-dom'
import { useWorkspaceStore } from '../../state/WorkspaceStore'
import { EmptyState } from '../../components/EmptyState'

function formatRelative(value: string): string {
  const date = new Date(value)
  if (Number.isNaN(date.getTime())) return value
  return date.toLocaleString()
}

export function HistoryTab() {
  const { workspaceId } = useParams<{ workspaceId: string }>()
  const id = Number(workspaceId)
  const { workspaceDetails, briefs } = useWorkspaceStore()
  const detail = workspaceDetails[id]
  const briefsForWorkspace = briefs[id] ?? []

  if (!detail) return <p className="muted">Loading…</p>

  return (
    <div className="history-tab">
      <section className="surface">
        <p className="surface-eyebrow">Search history</p>
        <h2 className="surface-title">Searches</h2>
        {detail.searches.length === 0 ? (
          <EmptyState title="No searches yet" description="Search history will collect here as you explore." />
        ) : (
          <ul className="dashboard-list">
            {detail.searches.map((search) => (
              <li key={search.id}>
                <div className="dashboard-list-row dashboard-list-row-static">
                  <span className="dashboard-list-icon">🔎</span>
                  <div className="dashboard-list-body">
                    <p className="dashboard-list-title">{search.query}</p>
                    <p className="dashboard-list-meta">
                      {search.result_count} results · {search.sources.join(', ') || 'all sources'} · {formatRelative(search.created_at)}
                    </p>
                  </div>
                </div>
              </li>
            ))}
          </ul>
        )}
      </section>

      <section className="surface">
        <p className="surface-eyebrow">Generated outputs</p>
        <h2 className="surface-title">Briefs &amp; reading paths</h2>
        {briefsForWorkspace.length === 0 ? (
          <EmptyState title="No outputs yet" description="Generated briefs and reading paths show here." />
        ) : (
          <ul className="dashboard-list">
            {briefsForWorkspace.map((brief) => (
              <li key={brief.createdAt}>
                <div className="dashboard-list-row dashboard-list-row-static">
                  <span className="dashboard-list-icon">✦</span>
                  <div className="dashboard-list-body">
                    <p className="dashboard-list-title">{brief.title}</p>
                    <p className="dashboard-list-meta">
                      {brief.mode} · {formatRelative(brief.createdAt)}
                    </p>
                  </div>
                </div>
              </li>
            ))}
          </ul>
        )}
      </section>
    </div>
  )
}
