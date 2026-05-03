import { useEffect, useMemo, useRef, useState } from 'react'
import { useNavigate } from 'react-router-dom'
import { useWorkspaceStore } from '../state/WorkspaceStore'

type Command = {
  id: string
  label: string
  hint?: string
  keywords?: string
  run: () => void | Promise<void>
}

export function CommandPalette() {
  const navigate = useNavigate()
  const { workspaces, createWorkspace } = useWorkspaceStore()
  const [isOpen, setIsOpen] = useState(false)
  const [query, setQuery] = useState('')
  const [activeIndex, setActiveIndex] = useState(0)
  const inputRef = useRef<HTMLInputElement>(null)

  useEffect(() => {
    function handleKey(event: KeyboardEvent) {
      const isMod = event.metaKey || event.ctrlKey
      if (isMod && event.key.toLowerCase() === 'k') {
        event.preventDefault()
        setIsOpen((value) => {
          const next = !value
          if (next) {
            queueMicrotask(() => {
              setQuery('')
              setActiveIndex(0)
              requestAnimationFrame(() => inputRef.current?.focus())
            })
          }
          return next
        })
      } else if (event.key === 'Escape' && isOpen) {
        setIsOpen(false)
      }
    }
    window.addEventListener('keydown', handleKey)
    return () => window.removeEventListener('keydown', handleKey)
  }, [isOpen])

  const commands = useMemo<Command[]>(() => {
    const result: Command[] = [
      {
        id: 'go-dashboard',
        label: 'Go to Dashboard',
        hint: 'Navigation',
        keywords: 'home overview',
        run: () => navigate('/'),
      },
      {
        id: 'go-library',
        label: 'Open Library',
        hint: 'Navigation',
        keywords: 'all saved papers',
        run: () => navigate('/library'),
      },
      {
        id: 'create-workspace',
        label: 'Create new workspace',
        hint: 'Action',
        keywords: 'new project',
        run: async () => {
          const created = await createWorkspace()
          if (created) navigate(`/workspaces/${created.id}/overview`)
        },
      },
    ]
    for (const workspace of workspaces) {
      result.push({
        id: `ws-${workspace.id}`,
        label: `Open: ${workspace.title}`,
        hint: `Workspace · ${workspace.saved_paper_count} saved`,
        keywords: workspace.title,
        run: () => navigate(`/workspaces/${workspace.id}/overview`),
      })
      result.push({
        id: `ws-${workspace.id}-search`,
        label: `Search in: ${workspace.title}`,
        hint: 'Workspace · Search',
        keywords: workspace.title,
        run: () => navigate(`/workspaces/${workspace.id}/search`),
      })
      result.push({
        id: `ws-${workspace.id}-rp`,
        label: `Reading path: ${workspace.title}`,
        hint: 'Workspace · Reading path',
        keywords: workspace.title,
        run: () => navigate(`/workspaces/${workspace.id}/reading-path`),
      })
    }
    return result
  }, [createWorkspace, navigate, workspaces])

  const filtered = useMemo(() => {
    const lowerQuery = query.trim().toLowerCase()
    if (!lowerQuery) return commands.slice(0, 12)
    return commands
      .filter((command) => {
        const haystack = `${command.label} ${command.keywords ?? ''}`.toLowerCase()
        return haystack.includes(lowerQuery)
      })
      .slice(0, 12)
  }, [commands, query])

  if (!isOpen) return null

  function runCommand(command: Command) {
    setIsOpen(false)
    void command.run()
  }

  return (
    <div className="command-palette-backdrop" role="dialog" aria-modal="true" onClick={() => setIsOpen(false)}>
      <div className="command-palette" onClick={(event) => event.stopPropagation()}>
        <input
          ref={inputRef}
          className="command-palette-input"
          placeholder="Type a command, page, or workspace…"
          value={query}
          onChange={(event) => {
            setQuery(event.target.value)
            setActiveIndex(0)
          }}
          onKeyDown={(event) => {
            if (event.key === 'ArrowDown') {
              event.preventDefault()
              setActiveIndex((index) => Math.min(index + 1, filtered.length - 1))
            } else if (event.key === 'ArrowUp') {
              event.preventDefault()
              setActiveIndex((index) => Math.max(index - 1, 0))
            } else if (event.key === 'Enter') {
              event.preventDefault()
              const command = filtered[activeIndex]
              if (command) runCommand(command)
            }
          }}
        />
        <ul className="command-palette-list">
          {filtered.length === 0 ? (
            <li className="command-palette-empty">No matches</li>
          ) : (
            filtered.map((command, index) => (
              <li key={command.id}>
                <button
                  className={`command-palette-item${index === activeIndex ? ' is-active' : ''}`}
                  type="button"
                  onMouseEnter={() => setActiveIndex(index)}
                  onClick={() => runCommand(command)}
                >
                  <span>{command.label}</span>
                  {command.hint && <span className="command-palette-hint">{command.hint}</span>}
                </button>
              </li>
            ))
          )}
        </ul>
        <div className="command-palette-footer">
          <span>↵ select</span>
          <span>↑↓ move</span>
          <span>esc close</span>
        </div>
      </div>
    </div>
  )
}
