import { useRef, useState } from 'react'
import { NavLink, Outlet, useLocation, useNavigate } from 'react-router-dom'
import { useWorkspaceStore } from '../state/WorkspaceStore'
import { CommandPalette } from './CommandPalette'
import { SelectionBar } from './SelectionBar'
import { ThemeToggle } from './ThemeToggle'
import { Toaster } from './Toaster'

const PRIMARY_NAV: Array<{ to: string; label: string; icon: string }> = [
  { to: '/', label: 'Dashboard', icon: '◧' },
  { to: '/library', label: 'Library', icon: '☷' },
]

interface NavTooltip {
  label: string
  icon: string
  y: number
}

export function AppShell() {
  const navigate = useNavigate()
  const location = useLocation()
  const { workspaces, createWorkspace, loadingWorkspaces } = useWorkspaceStore()
  const [collapsed, setCollapsed] = useState(
    () => typeof window !== 'undefined' && window.matchMedia('(max-width: 880px)').matches,
  )
  const [navTooltip, setNavTooltip] = useState<NavTooltip | null>(null)
  const tooltipHideTimer = useRef<ReturnType<typeof setTimeout> | null>(null)

  function showTooltip(e: React.MouseEvent<HTMLElement>, label: string, icon: string) {
    if (!collapsed) return
    if (tooltipHideTimer.current) clearTimeout(tooltipHideTimer.current)
    const rect = e.currentTarget.getBoundingClientRect()
    setNavTooltip({ label, icon, y: rect.top + rect.height / 2 })
  }

  function hideTooltip() {
    tooltipHideTimer.current = setTimeout(() => setNavTooltip(null), 80)
  }

  const activeWorkspaceId = (() => {
    const match = location.pathname.match(/^\/workspaces\/(\d+)/)
    return match ? Number(match[1]) : null
  })()

  async function handleCreateWorkspace() {
    const created = await createWorkspace()
    if (created) navigate(`/workspaces/${created.id}/overview`)
  }

  return (
    <div className={`app-shell-v2${collapsed ? ' is-collapsed' : ''}`}>
      <aside className="app-nav" aria-label="Primary navigation">
        <div className="app-nav-header">
          <div className="app-brand">
            <span className="app-brand-mark">RC</span>
            {!collapsed && (
              <div>
                <p className="app-brand-name">Research Companion</p>
                <p className="app-brand-tag">Find · Organize · Synthesize</p>
              </div>
            )}
          </div>
          <button
            className="icon-button"
            type="button"
            aria-label={collapsed ? 'Expand navigation' : 'Collapse navigation'}
            onClick={() => setCollapsed((value) => !value)}
          >
            {collapsed ? '»' : '«'}
          </button>
        </div>

        <nav className="app-nav-section" aria-label="Sections">
          <p className="app-nav-label">Workspace</p>
          <ul>
            {PRIMARY_NAV.map((item) => (
              <li key={item.to}>
                <NavLink
                  end={item.to === '/'}
                  to={item.to}
                  className={({ isActive }) => `app-nav-link${isActive ? ' is-active' : ''}`}
                  onMouseEnter={(e) => showTooltip(e, item.label, item.icon)}
                  onMouseLeave={hideTooltip}
                >
                  <span className="app-nav-icon" aria-hidden="true">{item.icon}</span>
                  <span className="app-nav-label-text">{item.label}</span>
                </NavLink>
              </li>
            ))}
          </ul>
        </nav>

        <nav className="app-nav-section app-nav-workspaces" aria-label="Workspaces">
          <div className="app-nav-section-header">
            <p className="app-nav-label">Projects</p>
            {!collapsed && (
              <button className="link-button" type="button" onClick={() => void handleCreateWorkspace()}>
                + New
              </button>
            )}
          </div>
          <ul>
            {loadingWorkspaces && workspaces.length === 0 ? (
              collapsed ? null : <li className="app-nav-empty">Loading…</li>
            ) : workspaces.length === 0 ? (
              collapsed ? null : (
                <li className="app-nav-empty">
                  No workspaces.{' '}
                  <button className="link-button" type="button" onClick={() => void handleCreateWorkspace()}>
                    Create one
                  </button>
                </li>
              )
            ) : (
              workspaces.map((workspace) => (
                <li key={workspace.id}>
                  <NavLink
                    to={`/workspaces/${workspace.id}/overview`}
                    title={workspace.title}
                    className={({ isActive }) => {
                      const expandedActive = isActive || activeWorkspaceId === workspace.id
                      return `app-nav-link app-nav-workspace${expandedActive ? ' is-active' : ''}`
                    }}
                    onMouseEnter={(e) => showTooltip(e, workspace.title, workspace.title.slice(0, 1).toUpperCase() || 'W')}
                    onMouseLeave={hideTooltip}
                  >
                    <span className="app-nav-icon workspace-initial" aria-hidden="true">
                      {workspace.title.slice(0, 1).toUpperCase() || 'W'}
                    </span>
                    <span className="app-nav-workspace-text">
                      <span className="app-nav-workspace-title">{workspace.title}</span>
                      <span className="app-nav-workspace-meta">
                        {workspace.saved_paper_count} saved · {workspace.search_count} searches
                      </span>
                    </span>
                  </NavLink>
                </li>
              ))
            )}
          </ul>
          {collapsed && (
            <button className="icon-button app-nav-create" type="button" onClick={() => void handleCreateWorkspace()} aria-label="Create workspace">
              +
            </button>
          )}
        </nav>

        <div className="app-nav-footer">
          {collapsed ? (
            <ThemeToggle compact />
          ) : (
            <>
              <ThemeToggle />
              <div className="app-nav-footer-hint">
                <kbd>⌘K</kbd>
                <span>Command palette</span>
              </div>
            </>
          )}
        </div>
      </aside>

      <main className="app-main">
        <Outlet />
      </main>

      <SelectionBar />
      <Toaster />
      <CommandPalette />

      {collapsed && navTooltip && (
        <div
          className="nav-tooltip"
          style={{ top: navTooltip.y }}
          onMouseEnter={() => { if (tooltipHideTimer.current) clearTimeout(tooltipHideTimer.current) }}
          onMouseLeave={hideTooltip}
        >
          <span className="nav-tooltip-icon">{navTooltip.icon}</span>
          <span>{navTooltip.label}</span>
        </div>
      )}
    </div>
  )
}
