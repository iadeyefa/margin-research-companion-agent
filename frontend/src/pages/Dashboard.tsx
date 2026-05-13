import { useEffect, useMemo, useState } from 'react'
import { Link, useNavigate } from 'react-router-dom'
import { api } from '../api/client'
import type { LibraryPaper, SearchHistory, WorkspaceDetail, WorkspaceSummary } from '../api/types'
import { EmptyState } from '../components/EmptyState'
import { PageLoading } from '../components/PageLoading'
import { PageHeader } from '../components/PageHeader'
import { SourceTag } from '../components/SourceTag'
import { useWorkspaceStore } from '../state/WorkspaceStore'

type RecentSearch = SearchHistory & { workspaceId: number; workspaceTitle: string }

function formatRelative(value: string): string {
  const date = new Date(value)
  if (Number.isNaN(date.getTime())) return value
  const diffMs = Date.now() - date.getTime()
  const minutes = Math.round(diffMs / 60000)
  if (minutes < 1) return 'just now'
  if (minutes < 60) return `${minutes}m ago`
  const hours = Math.round(minutes / 60)
  if (hours < 24) return `${hours}h ago`
  const days = Math.round(hours / 24)
  if (days < 30) return `${days}d ago`
  return date.toLocaleDateString()
}

export function DashboardPage() {
  const navigate = useNavigate()
  const { workspaces, createWorkspace } = useWorkspaceStore()
  const [details, setDetails] = useState<Record<number, WorkspaceDetail>>({})
  const [library, setLibrary] = useState<LibraryPaper[]>([])
  const [loadingLibrary, setLoadingLibrary] = useState(true)

  useEffect(() => {
    const state = { cancelled: false }
    async function loadDetails() {
      const recent = workspaces.slice(0, 5)
      const next: Record<number, WorkspaceDetail> = {}
      await Promise.all(
        recent.map(async (workspace) => {
          try {
            next[workspace.id] = await api.getWorkspace(workspace.id)
          } catch {
            // ignore individual failures
          }
        }),
      )
      if (!state.cancelled) setDetails(next)
    }
    if (workspaces.length > 0) {
      void loadDetails()
    }
    return () => {
      state.cancelled = true
    }
  }, [workspaces])

  useEffect(() => {
    const state = { cancelled: false }
    async function loadLibrary() {
      setLoadingLibrary(true)
      try {
        const data = await api.listLibrary()
        if (!state.cancelled) setLibrary(data)
      } catch {
        if (!state.cancelled) setLibrary([])
      } finally {
        if (!state.cancelled) setLoadingLibrary(false)
      }
    }
    void loadLibrary()
    return () => {
      state.cancelled = true
    }
  }, [])

  const recentWorkspaces: WorkspaceSummary[] = useMemo(() => workspaces.slice(0, 6), [workspaces])
  const totalSaved = useMemo(() => library.length, [library])

  const recentlySaved = useMemo(() => library.slice(0, 6), [library])

  const recentSearches = useMemo<RecentSearch[]>(() => {
    const all: RecentSearch[] = []
    for (const detail of Object.values(details)) {
      for (const search of detail.searches) {
        all.push({ ...search, workspaceId: detail.id, workspaceTitle: detail.title })
      }
    }
    return all
      .sort((a, b) => new Date(b.created_at).getTime() - new Date(a.created_at).getTime())
      .slice(0, 6)
  }, [details])

  const totalBriefs = useMemo(
    () => Object.values(details).reduce((sum, d) => sum + (d.briefs?.length ?? 0), 0),
    [details],
  )

  const recentBriefs = useMemo(() => {
    const all: Array<{
      workspaceId: number
      workspaceTitle: string
      title: string
      body: string
      mode: string
      createdAt: string
    }> = []
    for (const detail of Object.values(details)) {
      for (const brief of detail.briefs ?? []) {
        all.push({
          workspaceId: detail.id,
          workspaceTitle: detail.title,
          title: brief.title,
          body: brief.body,
          mode: brief.mode,
          createdAt: brief.created_at,
        })
      }
    }
    return all
      .sort((a, b) => new Date(b.createdAt).getTime() - new Date(a.createdAt).getTime())
      .slice(0, 4)
  }, [details])

  async function handleCreate() {
    const created = await createWorkspace()
    if (created) navigate(`/workspaces/${created.id}/overview`)
  }

  return (
    <div className="page page-dashboard">
      <PageHeader
        eyebrow="Dashboard"
        title="Welcome back"
        description="Pick up where you left off, or jump into something new."
        actions={
          <>
            <button className="pill-button is-primary" type="button" onClick={() => void handleCreate()}>
              + New workspace
            </button>
            <Link className="pill-button is-ghost" to="/library">
              Open library
            </Link>
          </>
        }
      />

      <section className="dashboard-stats">
        <article className="stat-card">
          <p className="stat-card-label">Workspaces</p>
          <p className="stat-card-value">{workspaces.length}</p>
        </article>
        <article className="stat-card">
          <p className="stat-card-label">Saved papers</p>
          <p className="stat-card-value">{loadingLibrary ? '—' : totalSaved}</p>
        </article>
        <article className="stat-card">
          <p className="stat-card-label">Recent searches</p>
          <p className="stat-card-value">{recentSearches.length}</p>
        </article>
        <article className="stat-card">
          <p className="stat-card-label">Saved briefs</p>
          <p className="stat-card-value">{totalBriefs}</p>
        </article>
      </section>

      <div className="dashboard-grid">
        <section className="surface">
          <div className="surface-header">
            <div>
              <p className="surface-eyebrow">Continue working</p>
              <h2 className="surface-title">Recent workspaces</h2>
            </div>
            <Link className="link-button" to="/library">
              View all
            </Link>
          </div>
          {recentWorkspaces.length === 0 ? (
            <EmptyState
              title="No workspaces yet"
              description="Create your first workspace to start collecting papers."
              action={
                <button className="pill-button is-primary" type="button" onClick={() => void handleCreate()}>
                  + New workspace
                </button>
              }
            />
          ) : (
            <div className="workspace-grid">
              {recentWorkspaces.map((workspace) => {
                const detail = details[workspace.id]
                const recentNote = detail?.notes?.split('\n')?.[0]
                return (
                  <Link
                    key={workspace.id}
                    to={`/workspaces/${workspace.id}/overview`}
                    className="workspace-tile"
                  >
                    <p className="workspace-tile-eyebrow">Workspace</p>
                    <h3>{workspace.title}</h3>
                    <p className="workspace-tile-meta">
                      {workspace.saved_paper_count} saved · {workspace.search_count} searches
                    </p>
                    {recentNote && <p className="workspace-tile-note">{recentNote}</p>}
                    <p className="workspace-tile-footer">Updated {formatRelative(workspace.updated_at)}</p>
                  </Link>
                )
              })}
            </div>
          )}
        </section>

        <section className="surface">
          <div className="surface-header">
            <div>
              <p className="surface-eyebrow">Saved this week</p>
              <h2 className="surface-title">Recently saved papers</h2>
            </div>
            <Link className="link-button" to="/library">
              Open library
            </Link>
          </div>
          {loadingLibrary ? (
            <>
              <PageLoading message="Loading recent saves…" dense />
              <ul className="dashboard-list-skel" aria-hidden>
                {[0, 1, 2, 3].map((i) => (
                  <li key={i} className="dashboard-list-row-skel">
                    <span className="ui-shimmer-bar" />
                    <span className="ui-shimmer-bar" />
                  </li>
                ))}
              </ul>
            </>
          ) : recentlySaved.length === 0 ? (
            <EmptyState title="Nothing saved yet" description="Saved papers from any workspace appear here." />
          ) : (
            <ul className="dashboard-list">
              {recentlySaved.map((paper) => (
                <li key={`${paper.source}-${paper.external_id}-${paper.workspace_id}`}>
                  <Link
                    to={`/papers/${encodeURIComponent(paper.source)}/${encodeURIComponent(paper.external_id)}`}
                    state={{ paper }}
                    className="dashboard-list-row"
                  >
                    <SourceTag source={paper.source} />
                    <div className="dashboard-list-body">
                      <p className="dashboard-list-title">{paper.title}</p>
                      <p className="dashboard-list-meta">
                        {paper.workspace_title} · {formatRelative(paper.saved_at)}
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
            <div>
              <p className="surface-eyebrow">Discovery</p>
              <h2 className="surface-title">Recent searches</h2>
            </div>
          </div>
          {recentSearches.length === 0 ? (
            <EmptyState title="No searches yet" description="Searches you run inside any workspace are listed here." />
          ) : (
            <ul className="dashboard-list">
              {recentSearches.map((search) => (
                <li key={`${search.workspaceId}-${search.id}`}>
                  <Link to={`/workspaces/${search.workspaceId}/search`} className="dashboard-list-row">
                    <span className="dashboard-list-icon">🔎</span>
                    <div className="dashboard-list-body">
                      <p className="dashboard-list-title">{search.query}</p>
                      <p className="dashboard-list-meta">
                        {search.workspaceTitle} · {search.result_count} results · {formatRelative(search.created_at)}
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
            <div>
              <p className="surface-eyebrow">Outputs</p>
              <h2 className="surface-title">Latest briefs</h2>
            </div>
          </div>
          {recentBriefs.length === 0 ? (
            <EmptyState
              title="No briefs yet"
              description="Synthesis runs and reading paths you generate will be saved here per workspace."
            />
          ) : (
            <ul className="dashboard-list">
              {recentBriefs.map((brief) => (
                <li key={`${brief.workspaceId}-${brief.createdAt}-${brief.title}`}>
                  <Link
                    to={`/workspaces/${brief.workspaceId}/synthesis`}
                    className="dashboard-list-row"
                  >
                    <span className="dashboard-list-icon">✦</span>
                    <div className="dashboard-list-body">
                      <p className="dashboard-list-title">{brief.title}</p>
                      <p className="dashboard-list-meta">
                        {brief.workspaceTitle} · {brief.mode} · {formatRelative(brief.createdAt)}
                      </p>
                    </div>
                  </Link>
                </li>
              ))}
            </ul>
          )}
        </section>
      </div>
    </div>
  )
}
