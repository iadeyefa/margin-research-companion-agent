import { useState } from 'react'
import { Link, useParams } from 'react-router-dom'
import { api } from '../../api/client'
import { paperKey, type Paper } from '../../api/types'
import { EmptyState } from '../../components/EmptyState'
import { useWorkspaceStore } from '../../state/WorkspaceStore'

type SynthesisMode = 'summary' | 'compare' | 'question' | 'extract'
type SynthesisStyle = 'balanced' | 'concise' | 'deep' | 'methods' | 'limitations'

const MODES: Array<{ key: SynthesisMode; label: string; description: string }> = [
  {
    key: 'summary',
    label: 'Summary brief',
    description: 'Cohesive paragraph synthesizing the selected papers.',
  },
  {
    key: 'compare',
    label: 'Compare',
    description: 'Side-by-side comparison of methods, results, and tradeoffs.',
  },
  {
    key: 'question',
    label: 'Ask',
    description: 'Answer a specific question across the selected papers.',
  },
  {
    key: 'extract',
    label: 'Extract',
    description: 'Pull out methods, datasets, findings, and limitations.',
  },
]

export function SynthesisTab() {
  const { workspaceId } = useParams<{ workspaceId: string }>()
  const id = Number(workspaceId)
  const { selection, workspaceDetails, recordBrief, deleteBrief, pushToast, togglePaperSelection } =
    useWorkspaceStore()
  const [mode, setMode] = useState<SynthesisMode>('summary')
  const [style, setStyle] = useState<SynthesisStyle>('balanced')
  const [question, setQuestion] = useState('')
  const [output, setOutput] = useState('')
  const [running, setRunning] = useState(false)

  const papers: Paper[] = selection.workspaceId === id ? selection.papers : []

  async function run() {
    if (papers.length === 0) {
      pushToast('Select at least one paper from Search or Saved.', 'error')
      return
    }
    if (mode === 'compare' && papers.length < 2) {
      pushToast('Select at least two papers to compare.', 'error')
      return
    }
    if (mode === 'question' && !question.trim()) {
      pushToast('Enter a question first.', 'error')
      return
    }
    setRunning(true)
    setOutput('')
    try {
      let body = ''
      let title = ''
      if (mode === 'extract') {
        const response = await api.synthesize({
          mode: 'question',
          style,
          question:
            'For each paper, extract the main method, datasets used, key findings, and limitations. Format the answer as a markdown list, one section per paper.',
          papers,
        })
        body = response.response
        title = `Extract · ${papers.length} papers`
      } else {
        const response = await api.synthesize({
          mode,
          style,
          question: mode === 'question' ? question.trim() : null,
          papers,
        })
        body = response.response
        if (mode === 'question') title = `Ask: ${question.trim()}`
        else if (mode === 'compare') title = `Compare · ${papers.length} papers`
        else title = `Summary · ${papers.length} papers`
      }
      setOutput(body)
      try {
        await recordBrief(id, { mode, style, title, body, source_papers: papers })
        pushToast('Brief generated and saved.', 'success')
      } catch (saveErr) {
        pushToast(
          saveErr instanceof Error
            ? `Synthesis finished, but saving the brief failed: ${saveErr.message}`
            : 'Synthesis finished, but saving the brief failed.',
          'error',
        )
      }
    } catch (caught) {
      pushToast(caught instanceof Error ? caught.message : 'Synthesis failed.', 'error')
    } finally {
      setRunning(false)
    }
  }

  const briefsForWorkspace = workspaceDetails[id]?.briefs ?? []

  return (
    <div className="synthesis-tab">
      <section className="surface">
        <div className="surface-header">
          <div>
            <p className="surface-eyebrow">Analysis studio</p>
            <h2 className="surface-title">Run synthesis on selected papers</h2>
          </div>
          <p className="muted">
            {papers.length} selected
            {papers.length === 0 && (
              <>
                {' '}
                · <Link to={`/workspaces/${id}/saved`}>pick from saved</Link>
              </>
            )}
          </p>
        </div>
        <div className="mode-tabs">
          {MODES.map((option) => (
            <button
              key={option.key}
              className={`mode-tab${mode === option.key ? ' is-active' : ''}`}
              type="button"
              onClick={() => setMode(option.key)}
            >
              <span className="mode-tab-label">{option.label}</span>
              <span className="mode-tab-hint">{option.description}</span>
            </button>
          ))}
        </div>

        <div className="synthesis-style-bar">
          <span className="synthesis-style-label">Style</span>
          <div className="synthesis-style-chips">
            {(
              [
                { value: 'balanced', label: 'Balanced' },
                { value: 'concise', label: 'Concise' },
                { value: 'deep', label: 'Deep' },
                { value: 'methods', label: 'Methods' },
                { value: 'limitations', label: 'Limitations' },
              ] as Array<{ value: SynthesisStyle; label: string }>
            ).map((option) => (
              <button
                key={option.value}
                type="button"
                className={`synthesis-style-chip${style === option.value ? ' is-active' : ''}`}
                onClick={() => setStyle(option.value)}
              >
                {option.label}
              </button>
            ))}
          </div>
        </div>

        {papers.length === 0 ? (
          <EmptyState
            icon="✳️"
            title="Nothing selected"
            description={
              <>
                Select papers from the <Link to={`/workspaces/${id}/saved`}>Saved</Link> or{' '}
                <Link to={`/workspaces/${id}/search`}>Search</Link> tabs to run analysis here.
              </>
            }
          />
        ) : (
          <ul className="selected-list">
            {papers.map((paper) => (
              <li key={paperKey(paper)} className="selected-list-row">
                <button
                  type="button"
                  className="selected-list-remove"
                  aria-label={`Remove ${paper.title} from selection`}
                  onClick={() => togglePaperSelection(id, paper)}
                >
                  ×
                </button>
                <div>
                  <p className="selected-list-title">{paper.title}</p>
                  <p className="selected-list-meta">
                    {paper.source} · {paper.year ?? 'n/a'} · {paper.authors.slice(0, 3).join(', ') || 'Unknown'}
                  </p>
                </div>
              </li>
            ))}
          </ul>
        )}

        {mode === 'question' && (
          <textarea
            className="question-input"
            placeholder="What evaluation method do these papers share?"
            rows={3}
            value={question}
            onChange={(event) => setQuestion(event.target.value)}
          />
        )}

        <div className="synthesis-action-row">
          <button
            className="pill-button is-primary"
            disabled={running || papers.length === 0}
            type="button"
            onClick={() => void run()}
          >
            {running ? 'Generating…' : `Run ${MODES.find((option) => option.key === mode)?.label}`}
          </button>
        </div>

        {output && (
          <article className="synthesis-output">
            <div className="synthesis-output-header">
              <span>Generated output</span>
              <button
                type="button"
                className="link-button"
                style={{ textTransform: 'none', letterSpacing: 'normal' }}
                onClick={() => {
                  void navigator.clipboard.writeText(output)
                  pushToast('Copied to clipboard', 'success')
                }}
              >
                Copy
              </button>
            </div>
            <div className="synthesis-output-body">
              {output.split('\n\n').map((block, i) => {
                const trimmed = block.trim()
                if (!trimmed) return null
                const isHeading =
                  trimmed.length < 80 && !trimmed.includes('. ') && /^[A-Z]/.test(trimmed)
                if (isHeading && output.split('\n\n').length > 2 && i > 0) {
                  return <span key={i} className="synthesis-output-section-heading">{trimmed}</span>
                }
                return <p key={i}>{trimmed}</p>
              })}
            </div>
          </article>
        )}
      </section>

      <section className="surface">
        <p className="surface-eyebrow">History</p>
        <h2 className="surface-title">Saved briefs</h2>
        {briefsForWorkspace.length === 0 ? (
          <EmptyState
            icon="📝"
            title="No briefs yet"
            description="Generated briefs from this workspace are stored here for future reference."
          />
        ) : (
          <ul className="brief-list">
            {briefsForWorkspace.map((brief) => (
              <li key={brief.id} className="brief-card">
                <div className="brief-card-header">
                  <div style={{ display: 'flex', alignItems: 'center', gap: 8 }}>
                    <span className="brief-mode">{brief.mode.replace('_', ' ')}</span>
                    {brief.style && brief.style !== 'balanced' && (
                      <span className="brief-style-badge">{brief.style}</span>
                    )}
                    {brief.source_papers?.length > 0 && (
                      <span className="brief-source-count">
                        📄 {brief.source_papers.length} papers
                      </span>
                    )}
                  </div>
                  <div className="brief-card-header-actions">
                    <span className="muted">{new Date(brief.created_at).toLocaleString()}</span>
                    <button
                      type="button"
                      className="link-button"
                      style={{ color: 'var(--error)' }}
                      onClick={() => {
                        if (
                          window.confirm(
                            `Remove this brief from history?\n\n${brief.title.slice(0, 80)}${brief.title.length > 80 ? '…' : ''}`,
                          )
                        ) {
                          void deleteBrief(id, brief.id)
                        }
                      }}
                    >
                      Delete
                    </button>
                  </div>
                </div>
                <div className="brief-card-body">
                  <p className="brief-title">{brief.title}</p>
                  <p className="brief-body">{brief.body}</p>
                  <div className="paper-actions">
                    <button
                      type="button"
                      className="pill-button is-ghost"
                      onClick={() => {
                        void navigator.clipboard.writeText(brief.body)
                        pushToast('Brief copied to clipboard', 'success')
                      }}
                    >
                      Copy
                    </button>
                    <button
                      type="button"
                      className="pill-button is-ghost"
                      onClick={() => {
                        setOutput(brief.body)
                        if (brief.mode === 'summary' || brief.mode === 'compare' || brief.mode === 'question') {
                          setMode(brief.mode)
                        }
                      }}
                    >
                      Reopen
                    </button>
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
