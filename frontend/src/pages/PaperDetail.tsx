import { useEffect, useMemo, useState } from 'react'
import { Link, useLocation, useNavigate, useParams } from 'react-router-dom'
import { api } from '../api/client'
import type { LibraryPaper, Paper } from '../api/types'
import { paperKey } from '../api/types'
import { PageHeader } from '../components/PageHeader'
import { SourceTag } from '../components/SourceTag'
import { EmptyState } from '../components/EmptyState'
import { useWorkspaceStore } from '../state/WorkspaceStore'

type LocationState = { paper?: Paper; workspaceId?: number }

export function PaperDetailPage() {
  const navigate = useNavigate()
  const params = useParams<{ source: string; externalId: string }>()
  const location = useLocation()
  const state = (location.state ?? {}) as LocationState
  const { workspaces, refreshWorkspaces, savePaper, removePaper, togglePaperSelection, isSelected, selection } =
    useWorkspaceStore()

  const [libraryEntry, setLibraryEntry] = useState<LibraryPaper | null>(null)
  const [loading, setLoading] = useState(true)
  const [chosenWorkspace, setChosenWorkspace] = useState<number | null>(state.workspaceId ?? null)

  const decodedSource = params.source ? decodeURIComponent(params.source) : ''
  const decodedExternalId = params.externalId ? decodeURIComponent(params.externalId) : ''

  useEffect(() => {
    void refreshWorkspaces()
  }, [refreshWorkspaces])

  useEffect(() => {
    let cancelled = false
    async function load() {
      setLoading(true)
      try {
        const data = await api.listLibrary()
        if (!cancelled) {
          const match = data.find(
            (paper) => paper.source === decodedSource && paper.external_id === decodedExternalId,
          )
          setLibraryEntry(match ?? null)
        }
      } finally {
        if (!cancelled) setLoading(false)
      }
    }
    void load()
    return () => {
      cancelled = true
    }
  }, [decodedSource, decodedExternalId, workspaces.length])

  const paper: Paper | null = useMemo(() => {
    if (libraryEntry) return libraryEntry
    if (state.paper) return state.paper
    return null
  }, [libraryEntry, state.paper])

  const containingWorkspaces = useMemo(() => {
    if (!libraryEntry) return [] as Array<{ id: number; title: string }>
    return [{ id: libraryEntry.workspace_id, title: libraryEntry.workspace_title }]
  }, [libraryEntry])

  if (loading && !paper) {
    return (
      <div className="page">
        <p className="muted">Loading paper…</p>
      </div>
    )
  }

  if (!paper) {
    return (
      <div className="page">
        <PageHeader eyebrow="Paper" title="Paper unavailable" />
        <EmptyState
          title="We don't have this paper cached"
          description="Open it from a search result or library entry to view full metadata."
          action={
            <button className="pill-button is-ghost" type="button" onClick={() => navigate(-1)}>
              Go back
            </button>
          }
        />
      </div>
    )
  }

  const selected = isSelected(paper)
  const targetWorkspaceId = chosenWorkspace ?? selection.workspaceId ?? workspaces[0]?.id ?? null

  async function handleSave() {
    if (targetWorkspaceId == null) return
    await savePaper(targetWorkspaceId, paper as Paper)
  }

  async function handleRemove(workspaceId: number) {
    await removePaper(workspaceId, paper as Paper)
  }

  return (
    <div className="page page-paper">
      <PageHeader
        eyebrow="Paper"
        title={paper.title}
        description={
          <span className="paper-detail-meta">
            <SourceTag source={paper.source} />
            {paper.year && <span className="paper-pill">{paper.year}</span>}
            {paper.citation_count != null && paper.citation_count > 0 && (
              <span className="paper-pill">{paper.citation_count.toLocaleString()} cited</span>
            )}
            {paper.open_access && <span className="paper-pill paper-pill-accent">Open access</span>}
            {paper.doi && <span className="paper-pill">DOI</span>}
          </span>
        }
        actions={
          <>
            <button
              className={`pill-button${selected ? ' is-ghost' : ' is-primary'}`}
              type="button"
              onClick={() => {
                if (targetWorkspaceId == null) return
                togglePaperSelection(targetWorkspaceId, paper as Paper)
              }}
              disabled={targetWorkspaceId == null}
            >
              {selected ? 'Remove from selection' : 'Add to selection'}
            </button>
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
          </>
        }
      />

      <div className="paper-detail-grid">
        <section className="surface">
          <p className="surface-eyebrow">Authors</p>
          <p className="paper-detail-authors">
            {paper.authors.length > 0 ? paper.authors.join(', ') : 'Unknown authors'}
          </p>
          {paper.venue && <p className="muted paper-detail-venue">{paper.venue}{paper.publication_date ? ` · ${paper.publication_date}` : ''}</p>}

          <p className="surface-eyebrow paper-detail-section-label">Abstract</p>
          {paper.abstract ? (
            <p className="paper-detail-abstract">{paper.abstract}</p>
          ) : (
            <p className="muted">No abstract available from this source.</p>
          )}
        </section>

        <aside className="surface paper-detail-side">
          <p className="surface-eyebrow">Add to workspace</p>
          {workspaces.length === 0 ? (
            <p className="muted">Create a workspace first to save this paper.</p>
          ) : (
            <>
              <select
                className="paper-detail-select"
                value={targetWorkspaceId ?? ''}
                onChange={(event) => setChosenWorkspace(Number(event.target.value))}
              >
                {workspaces.map((workspace) => (
                  <option key={workspace.id} value={workspace.id}>
                    {workspace.title}
                  </option>
                ))}
              </select>
              <button
                className="pill-button is-primary"
                type="button"
                onClick={() => void handleSave()}
                disabled={targetWorkspaceId == null}
              >
                Save here
              </button>
            </>
          )}

          <p className="surface-eyebrow paper-detail-section-label">In your library</p>
          {containingWorkspaces.length === 0 ? (
            <p className="muted">Not yet saved in any workspace.</p>
          ) : (
            <ul className="paper-detail-workspace-list">
              {containingWorkspaces.map((workspace) => (
                <li key={workspace.id}>
                  <Link to={`/workspaces/${workspace.id}/saved`} className="link-button">
                    {workspace.title}
                  </Link>
                  <button
                    className="link-button"
                    type="button"
                    onClick={() => void handleRemove(workspace.id)}
                  >
                    Remove
                  </button>
                </li>
              ))}
            </ul>
          )}

          <p className="surface-eyebrow paper-detail-section-label">Identifiers</p>
          <dl className="paper-detail-meta-list">
            <div>
              <dt>Source</dt>
              <dd>{paper.source}</dd>
            </div>
            <div>
              <dt>External ID</dt>
              <dd className="break-all">{paper.external_id}</dd>
            </div>
            {paper.doi && (
              <div>
                <dt>DOI</dt>
                <dd>
                  <a href={`https://doi.org/${paper.doi}`} rel="noreferrer" target="_blank">
                    {paper.doi}
                  </a>
                </dd>
              </div>
            )}
          </dl>

          <p className="surface-eyebrow paper-detail-section-label">Quick actions</p>
          <div className="paper-detail-actions">
            <button
              className="pill-button is-ghost"
              type="button"
              disabled={targetWorkspaceId == null}
              onClick={() => {
                if (targetWorkspaceId == null) return
                togglePaperSelection(targetWorkspaceId, paper as Paper)
                navigate(`/workspaces/${targetWorkspaceId}/synthesis`)
              }}
            >
              Compare in synthesis
            </button>
            <button
              className="pill-button is-ghost"
              type="button"
              disabled={targetWorkspaceId == null}
              onClick={() => {
                if (targetWorkspaceId == null) return
                togglePaperSelection(targetWorkspaceId, paper as Paper)
                navigate(`/workspaces/${targetWorkspaceId}/reading-path`)
              }}
            >
              Add to reading path
            </button>
            <button
              className="pill-button is-ghost"
              type="button"
              onClick={async () => {
                try {
                  const response = await api.exportPapers({ format: 'bibtex', papers: [paper as Paper] })
                  await navigator.clipboard.writeText(response.content)
                } catch {
                  // ignore
                }
              }}
            >
              Copy BibTeX
            </button>
          </div>
        </aside>
      </div>
    </div>
  )
}

export { paperKey }
