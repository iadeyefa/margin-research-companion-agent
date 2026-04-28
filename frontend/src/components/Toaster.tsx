import { useWorkspaceStore } from '../state/WorkspaceStore'

export function Toaster() {
  const { toasts, dismissToast } = useWorkspaceStore()
  if (toasts.length === 0) return null
  return (
    <div className="toast-stack" role="status" aria-live="polite">
      {toasts.map((toast) => (
        <button
          key={toast.id}
          className={`toast tone-${toast.tone}`}
          type="button"
          onClick={() => dismissToast(toast.id)}
        >
          {toast.message}
        </button>
      ))}
    </div>
  )
}
