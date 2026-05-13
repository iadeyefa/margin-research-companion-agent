type PageLoadingProps = {
  message?: string
  dense?: boolean
}

export function PageLoading({ message = 'Loading…', dense }: PageLoadingProps) {
  return (
    <div className={`page-loading${dense ? ' page-loading-dense' : ''}`} role="status" aria-live="polite" aria-busy="true">
      <span className="page-loading-spinner" aria-hidden />
      <span className="page-loading-text">{message}</span>
    </div>
  )
}
