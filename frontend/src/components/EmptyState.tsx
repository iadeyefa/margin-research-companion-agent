import type { ReactNode } from 'react'

type EmptyStateProps = {
  title: string
  description?: ReactNode
  action?: ReactNode
  size?: 'sm' | 'md' | 'lg'
  icon?: string
}

export function EmptyState({ title, description, action, size = 'md', icon }: EmptyStateProps) {
  return (
    <div className={`empty-state empty-state-${size}`}>
      {icon && <div className="empty-state-icon">{icon}</div>}
      <p className="empty-state-title">{title}</p>
      {description && <p className="empty-state-description">{description}</p>}
      {action && <div className="empty-state-action">{action}</div>}
    </div>
  )
}
