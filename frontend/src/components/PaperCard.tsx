import { useState } from 'react'
import { Link } from 'react-router-dom'
import type { Paper } from '../api/types'
import { SourceTag } from './SourceTag'

type PaperCardProps = {
  paper: Paper
  isSelected: boolean
  isSaved?: boolean
  onToggleSelect: (paper: Paper) => void
  onSave?: (paper: Paper) => void
  onRemove?: (paper: Paper) => void
  variant?: 'full' | 'compact'
}

export function PaperCard({
  paper,
  isSelected,
  isSaved,
  onToggleSelect,
  onSave,
  onRemove,
  variant = 'full',
}: PaperCardProps) {
  const [showFullAbstract, setShowFullAbstract] = useState(false)
  const detailRoute = `/papers/${encodeURIComponent(paper.source)}/${encodeURIComponent(paper.external_id)}`
  const abstract = paper.abstract ?? ''
  const isLongAbstract = abstract.length > 280
  const visibleAbstract = !showFullAbstract && isLongAbstract ? `${abstract.slice(0, 280).trimEnd()}…` : abstract

  return (
    <article className={`paper-card${isSelected ? ' selected' : ''}${variant === 'compact' ? ' compact' : ''}`}>
      <div className="paper-card-row">
        <label className="paper-checkbox" aria-label={`Select ${paper.title}`}>
          <input
            checked={isSelected}
            onChange={() => onToggleSelect(paper)}
            type="checkbox"
          />
        </label>
        <div className="paper-card-body">
          <div className="paper-card-header">
            <SourceTag source={paper.source} />
            {paper.year && <span className="paper-year">{paper.year}</span>}
            {paper.citation_count != null && paper.citation_count > 0 && (
              <span className="paper-pill" title={`${paper.citation_count} citations`}>
                {paper.citation_count.toLocaleString()} cited
              </span>
            )}
            {paper.open_access && <span className="paper-pill paper-pill-accent">Open access</span>}
            {paper.doi && <span className="paper-pill">DOI</span>}
          </div>
          <h3 className="paper-title">
            <Link
              state={{ paper }}
              to={detailRoute}
              onClick={(event) => event.stopPropagation()}
            >
              {paper.title}
            </Link>
          </h3>
          <p className="paper-meta">
            {paper.authors.slice(0, 4).join(', ') || 'Unknown authors'}
            {paper.authors.length > 4 ? ` +${paper.authors.length - 4}` : ''}
            {paper.venue ? ` · ${paper.venue}` : ''}
            {paper.publication_date && !paper.year ? ` · ${paper.publication_date}` : ''}
          </p>
          {variant === 'full' && abstract && (
            <p className="paper-abstract">
              {visibleAbstract}
              {isLongAbstract && (
                <button
                  className="link-button"
                  type="button"
                  onClick={() => setShowFullAbstract((value) => !value)}
                >
                  {showFullAbstract ? 'Show less' : 'Show more'}
                </button>
              )}
            </p>
          )}
          <div className="paper-actions">
            {onSave && (
              <button
                className={`pill-button${isSaved ? ' is-saved' : ' is-primary'}`}
                disabled={isSaved}
                type="button"
                onClick={() => onSave(paper)}
              >
                {isSaved ? '✓ Saved' : 'Save'}
              </button>
            )}
            {onRemove && (
              <button className="pill-button" type="button" onClick={() => onRemove(paper)}>
                Remove
              </button>
            )}
            <Link state={{ paper }} className="pill-button is-ghost" to={detailRoute}>
              Open detail
            </Link>
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
          </div>
        </div>
      </div>
    </article>
  )
}
