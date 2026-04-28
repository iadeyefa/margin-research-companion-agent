import { Component, type ErrorInfo, type ReactNode } from 'react'

type Props = {
  children: ReactNode
}

type State = {
  hasError: boolean
  message: string
}

class ErrorBoundary extends Component<Props, State> {
  state: State = {
    hasError: false,
    message: '',
  }

  static getDerivedStateFromError(error: Error): State {
    return {
      hasError: true,
      message: error.message || 'The app hit an unexpected error.',
    }
  }

  componentDidCatch(error: Error, errorInfo: ErrorInfo) {
    console.error('Research Companion frontend error:', error, errorInfo)
  }

  render() {
    if (this.state.hasError) {
      return (
        <main className="page" style={{ padding: 32 }}>
          <section className="surface" style={{ maxWidth: 720 }}>
            <p className="surface-eyebrow">Research Companion</p>
            <h1 className="surface-title">Frontend error</h1>
            <p className="muted">
              The app hit a runtime error while rendering. Refresh once after the backend is running, and if it still fails,
              check the browser console.
            </p>
            <pre style={{ background: '#fff5f5', padding: 12, borderRadius: 8, overflowX: 'auto' }}>
              {this.state.message}
            </pre>
          </section>
        </main>
      )
    }

    return this.props.children
  }
}

export default ErrorBoundary
