import { useState } from 'react'
import { useNavigate } from 'react-router-dom'
import { api } from '../api/client'
import { useWorkspaceStore } from '../state/WorkspaceStore'

export function SelectionBar() {
  const navigate = useNavigate()
  const { selection, clearSelection, pushToast } = useWorkspaceStore()
  const [isExporting, setIsExporting] = useState(false)

  if (selection.papers.length === 0 || selection.workspaceId === null) return null

  async function exportPapers(format: 'bibtex' | 'markdown') {
    setIsExporting(true)
    try {
      const response = await api.exportPapers({ format, papers: selection.papers })
      await navigator.clipboard.writeText(response.content)
      pushToast(
        `${format === 'bibtex' ? 'BibTeX' : 'Markdown'} for ${selection.papers.length} papers copied to clipboard.`,
        'success',
      )
    } catch (caught) {
      pushToast(caught instanceof Error ? caught.message : 'Failed to export papers.', 'error')
    } finally {
      setIsExporting(false)
    }
  }

  return (
    <div className="selection-bar" role="region" aria-label="Selected papers">
      <div className="selection-bar-summary">
        <strong>{selection.papers.length}</strong>
        <span>selected</span>
      </div>
      <div className="selection-bar-actions">
        <button
          className="pill-button is-primary"
          type="button"
          onClick={() => navigate(`/workspaces/${selection.workspaceId}/synthesis`)}
        >
          Synthesize
        </button>
        <button
          className="pill-button is-ghost"
          type="button"
          onClick={() => navigate(`/workspaces/${selection.workspaceId}/reading-path`)}
        >
          Build reading path
        </button>
        <button className="pill-button is-ghost" disabled={isExporting} type="button" onClick={() => void exportPapers('bibtex')}>
          BibTeX
        </button>
        <button className="pill-button is-ghost" disabled={isExporting} type="button" onClick={() => void exportPapers('markdown')}>
          Markdown
        </button>
        <button className="pill-button is-ghost" type="button" onClick={clearSelection}>
          Clear
        </button>
      </div>
    </div>
  )
}
