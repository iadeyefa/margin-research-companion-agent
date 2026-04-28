import type { ReactNode } from 'react'

type PageHeaderProps = {
  eyebrow?: string
  title: string
  description?: ReactNode
  actions?: ReactNode
}

export function PageHeader({ eyebrow, title, description, actions }: PageHeaderProps) {
  return (
    <header className="page-header">
      <div className="page-header-text">
        {eyebrow && <p className="page-header-eyebrow">{eyebrow}</p>}
        <h1 className="page-header-title">{title}</h1>
        {description && <p className="page-header-description">{description}</p>}
      </div>
      {actions && <div className="page-header-actions">{actions}</div>}
    </header>
  )
}
