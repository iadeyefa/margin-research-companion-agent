import { useState } from 'react'
import { Link, useParams } from 'react-router-dom'
import { api } from '../../api/client'
import type { Paper, ReadingPathResponse } from '../../api/types'
import { EmptyState } from '../../components/EmptyState'
import { useWorkspaceStore } from '../../state/WorkspaceStore'

type ProgressKey = string

const PRESET_GOALS = [
  { label: 'Fast overview', objective: 'Give me the fastest path to a working overview of this topic.' },
  { label: 'Starter path', objective: 'Recommend a beginner-friendly reading order, easiest first.' },
  { label: 'Deep dive', objective: 'Sequence these papers for a deep methodological dive, including foundational background first.' },
]

export function ReadingPathTab() {
  const { workspaceId } = useParams<{ workspaceId: string }>()
  const id = Number(workspaceId)
  const { selection, workspaceDetails, recordBrief, pushToast } = useWorkspaceStore()
  const detail = workspaceDetails[id]
  const [objective, setObjective] = useState('')
  const [running, setRunning] = useState(false)
  const [path, setPath] = useState<ReadingPathResponse | null>(null)
  const [progress, setProgress] = useState<Record<ProgressKey, 'unread' | 'reading' | 'done'>>({})
  const [stepNotes, setStepNotes] = useState<Record<ProgressKey, string>>({})
  const [orderOverride, setOrderOverride] = useState<string[] | null>(null)

  const fallbackPapers: Paper[] = detail?.saved_papers ?? []
  const papers = selection.workspaceId === id && selection.papers.length > 0 ? selection.papers : fallbackPapers

  async function generate(presetObjective?: string) {
    const objectiveValue = (presetObjective ?? objective).trim() || null
    if (papers.length === 0) {
      pushToast('Select papers in Saved or Search first.', 'error')
      return
    }
    setRunning(true)
    try {
      const response = await api.buildReadingPath({ objective: objectiveValue, papers })
      setPath(response)
      setOrderOverride(null)
      const initialProgress: Record<ProgressKey, 'unread' | 'reading' | 'done'> = {}
      for (const step of response.steps) {
        initialProgress[`${step.source}::${step.external_id}`] = 'unread'
      }
      setProgress(initialProgress)
      try {
        await recordBrief(id, {
          mode: 'reading_path',
          style: 'balanced',
          title: `Reading path · ${response.steps.length} steps`,
          body: `${response.objective}\n\n${response.overview}\n\n${response.steps
            .map((step) => `${step.order}. ${step.title}\n   ${step.rationale}`)
            .join('\n\n')}`,
          source_papers: papers,
        })
        pushToast('Reading path generated and saved.', 'success')
      } catch (saveErr) {
        pushToast(
          saveErr instanceof Error
            ? `Reading path ready, but saving history failed: ${saveErr.message}`
            : 'Reading path ready, but saving history failed.',
          'error',
        )
      }
    } catch (caught) {
      pushToast(caught instanceof Error ? caught.message : 'Failed to build reading path.', 'error')
    } finally {
      setRunning(false)
    }
  }

  const orderedKeys = path
    ? orderOverride ?? path.steps.map((step) => `${step.source}::${step.external_id}`)
    : []
  const stepsByKey = new Map(
    (path?.steps ?? []).map((step) => [`${step.source}::${step.external_id}`, step]),
  )

  function move(key: string, direction: -1 | 1) {
    if (!path) return
    const keys = orderedKeys.slice()
    const index = keys.indexOf(key)
    const next = index + direction
    if (index === -1 || next < 0 || next >= keys.length) return
    keys.splice(next, 0, ...keys.splice(index, 1))
    setOrderOverride(keys)
  }

  const completed = Object.values(progress).filter((value) => value === 'done').length

  return (
    <div className="reading-path-tab">
      <section className="surface">
        <div className="surface-header">
          <div>
            <p className="surface-eyebrow">Reading path</p>
            <h2 className="surface-title">Sequence selected papers into a guided read</h2>
          </div>
          <p className="muted">
            {papers.length} papers
            {selection.workspaceId !== id && fallbackPapers.length > 0 && ' (using saved)'}
            {papers.length === 0 && (
              <>
                {' '}
                · <Link to={`/workspaces/${id}/saved`}>pick from saved</Link>
              </>
            )}
          </p>
        </div>
        <div className="path-goal-row">
          <input
            className="search-input"
            placeholder="Optional reading goal: e.g. learn the basics fast or compare evaluation methods"
            value={objective}
            onChange={(event) => setObjective(event.target.value)}
          />
          <button className="pill-button is-primary" type="button" disabled={running || papers.length === 0} onClick={() => void generate()}>
            {running ? 'Planning…' : path ? 'Regenerate' : 'Build path'}
          </button>
        </div>
        <div className="preset-row">
          {PRESET_GOALS.map((preset) => (
            <button
              key={preset.label}
              className="suggestion-chip"
              type="button"
              disabled={running || papers.length === 0}
              onClick={() => {
                setObjective(preset.objective)
                void generate(preset.objective)
              }}
            >
              {preset.label}
            </button>
          ))}
        </div>
      </section>

      {!path ? (
        <EmptyState
          size="lg"
          icon="🗺️"
          title="No path generated yet"
          description={
            papers.length === 0
              ? 'Select papers from Saved or Search to build a reading path.'
              : 'Pick a preset above or enter a goal, then click Build path.'
          }
        />
      ) : (
        <section className="surface">
          <div className="surface-header">
            <div>
              <p className="surface-eyebrow">{path.objective}</p>
              <h2 className="surface-title">Plan</h2>
            </div>
            <p className="muted">
              {completed} / {path.steps.length} read
            </p>
          </div>
          <p className="path-overview">{path.overview}</p>

          <ol className="reading-path-list">
            {orderedKeys.map((key, index) => {
              const step = stepsByKey.get(key)
              if (!step) return null
              const status = progress[key] ?? 'unread'
              const note = stepNotes[key] ?? ''
              return (
                <li key={key} className={`reading-step status-${status}`}>
                  <div className="reading-step-order">{index + 1}</div>
                  <div className="reading-step-body">
                    <div className="reading-step-header">
                      <h3>
                        <Link
                          to={`/papers/${encodeURIComponent(step.source)}/${encodeURIComponent(step.external_id)}`}
                        >
                          {step.title}
                        </Link>
                      </h3>
                      <div className="reading-step-controls">
                        <button type="button" className="link-button" disabled={index === 0} onClick={() => move(key, -1)}>
                          ↑
                        </button>
                        <button
                          type="button"
                          className="link-button"
                          disabled={index === orderedKeys.length - 1}
                          onClick={() => move(key, 1)}
                        >
                          ↓
                        </button>
                      </div>
                    </div>
                    <p className="reading-step-meta">{step.source}</p>
                    <p className="reading-step-rationale">
                      <strong>Why this comes next:</strong> {step.rationale}
                    </p>
                    <div className="reading-step-actions">
                      <button
                        type="button"
                        className={`reading-step-status-btn${status === 'reading' ? ' is-reading' : status === 'done' ? ' is-done' : ''}`}
                        onClick={() =>
                          setProgress((current) => ({
                            ...current,
                            [key]: status === 'unread' ? 'reading' : status === 'reading' ? 'done' : 'unread',
                          }))
                        }
                      >
                        {status === 'unread' ? '○ Start reading' : status === 'reading' ? '◉ Reading…' : '✓ Done'}
                      </button>
                    </div>
                    <textarea
                      className="reading-step-note"
                      placeholder="Notes on this step (optional)"
                      rows={2}
                      value={note}
                      onChange={(event) =>
                        setStepNotes((current) => ({ ...current, [key]: event.target.value }))
                      }
                    />
                  </div>
                </li>
              )
            })}
          </ol>
        </section>
      )}
    </div>
  )
}
