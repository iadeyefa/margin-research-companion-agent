import { useEffect, useRef, useState } from 'react'
import { useParams } from 'react-router-dom'
import { EmptyState } from '../../components/EmptyState'
import { useWorkspaceStore } from '../../state/WorkspaceStore'

export function NotesTab() {
  const { workspaceId } = useParams<{ workspaceId: string }>()
  const id = Number(workspaceId)
  const { workspaceDetails, updateWorkspace } = useWorkspaceStore()
  const detail = workspaceDetails[id]
  const [draft, setDraft] = useState(detail?.notes ?? '')
  const [savedAt, setSavedAt] = useState<number | null>(null)
  const [isDirty, setIsDirty] = useState(false)
  const timerRef = useRef<number | null>(null)

  useEffect(() => {
    setDraft(detail?.notes ?? '')
    setIsDirty(false)
    setSavedAt(null)
  }, [detail?.id, detail?.notes])

  useEffect(() => {
    if (!isDirty) return
    if (timerRef.current) window.clearTimeout(timerRef.current)
    timerRef.current = window.setTimeout(async () => {
      const summary = await updateWorkspace(id, { notes: draft })
      if (summary) {
        setSavedAt(Date.now())
        setIsDirty(false)
      }
    }, 1200)
    return () => {
      if (timerRef.current) window.clearTimeout(timerRef.current)
    }
  }, [draft, id, isDirty, updateWorkspace])

  if (!detail) return <p className="muted">Loading…</p>

  const status = isDirty ? 'Saving…' : savedAt ? `Saved ${new Date(savedAt).toLocaleTimeString()}` : 'All changes saved'

  return (
    <div className="notes-tab">
      <section className="surface notes-surface">
        <div className="surface-header">
          <div>
            <p className="surface-eyebrow">Notebook</p>
            <h2 className="surface-title">Project notes</h2>
          </div>
          <span className="muted notes-status">{status}</span>
        </div>
        <textarea
          className="notes-input"
          rows={20}
          placeholder="Capture takeaways, hypotheses, citation networks, open questions…"
          value={draft}
          onChange={(event) => {
            setDraft(event.target.value)
            setIsDirty(true)
          }}
        />
        {draft.length === 0 && (
          <EmptyState
            size="sm"
            title="Tip"
            description="Use one heading per area: # Findings, # Open questions, # Methods I want to try…"
          />
        )}
      </section>
    </div>
  )
}
