import { useEffect, useState } from 'react'
import { NavLink, Outlet, useNavigate, useParams } from 'react-router-dom'
import { useWorkspaceStore } from '../../state/WorkspaceStore'

const TABS: Array<{ to: string; label: string }> = [
  { to: 'overview', label: 'Overview' },
  { to: 'search', label: 'Search' },
  { to: 'saved', label: 'Saved' },
  { to: 'synthesis', label: 'Synthesis' },
  { to: 'reading-path', label: 'Reading path' },
  { to: 'notes', label: 'Notes' },
  { to: 'history', label: 'History' },
]

export function WorkspaceLayout() {
  const { workspaceId } = useParams<{ workspaceId: string }>()
  const navigate = useNavigate()
  const { workspaces, workspaceDetails, refreshWorkspace, updateWorkspace, deleteWorkspace, clearSelection } = useWorkspaceStore()
  const id = workspaceId ? Number(workspaceId) : null
  const [renameDraft, setRenameDraft] = useState('')
  const [isRenaming, setIsRenaming] = useState(false)

  useEffect(() => {
    if (id !== null) {
      void refreshWorkspace(id)
    }
  }, [id, refreshWorkspace])

  const summary = id !== null ? workspaces.find((workspace) => workspace.id === id) : null
  const detail = id !== null ? workspaceDetails[id] : null
  const title = summary?.title ?? detail?.title ?? 'Workspace'

  async function handleRenameSubmit(event: React.FormEvent) {
    event.preventDefault()
    if (id === null) return
    const next = renameDraft.trim()
    if (next.length === 0 || next === title) {
      setIsRenaming(false)
      return
    }
    await updateWorkspace(id, { title: next })
    setIsRenaming(false)
  }

  async function handleDelete() {
    if (id === null) return
    const ok = window.confirm(`Delete workspace "${title}"? This removes all saved papers and history.`)
    if (!ok) return
    await deleteWorkspace(id)
    clearSelection()
    navigate('/')
  }

  if (id === null || Number.isNaN(id)) {
    return <p className="muted page">Workspace not found.</p>
  }

  return (
    <div className="workspace-shell">
      <header className="workspace-header">
        <div className="workspace-header-text">
          <p className="page-header-eyebrow">Workspace</p>
          {isRenaming ? (
            <form onSubmit={handleRenameSubmit} className="workspace-rename-form">
              <input
                autoFocus
                className="workspace-rename-input"
                value={renameDraft}
                onChange={(event) => setRenameDraft(event.target.value)}
                onBlur={() => setIsRenaming(false)}
                onKeyDown={(event) => {
                  if (event.key === 'Escape') {
                    setIsRenaming(false)
                  }
                }}
              />
            </form>
          ) : (
            <h1
              className="page-header-title workspace-title"
              onDoubleClick={() => {
                setRenameDraft(title)
                setIsRenaming(true)
              }}
              title="Double-click to rename"
            >
              {title}
            </h1>
          )}
          <p className="page-header-description">
            {summary?.saved_paper_count ?? detail?.saved_paper_count ?? 0} saved · {summary?.search_count ?? detail?.search_count ?? 0} searches
          </p>
        </div>
        <div className="workspace-header-actions">
          <button
            className="pill-button is-ghost"
            type="button"
            onClick={() => {
              setRenameDraft(title)
              setIsRenaming(true)
            }}
          >
            Rename
          </button>
          <button className="pill-button is-ghost" type="button" onClick={() => void handleDelete()}>
            Delete
          </button>
        </div>
      </header>

      <nav className="workspace-tabs" aria-label="Workspace sections">
        {TABS.map((tab) => (
          <NavLink
            key={tab.to}
            to={tab.to}
            className={({ isActive }) => `workspace-tab${isActive ? ' is-active' : ''}`}
          >
            {tab.label}
          </NavLink>
        ))}
      </nav>

      <div className="workspace-tab-content">
        <Outlet />
      </div>
    </div>
  )
}
