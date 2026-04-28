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
        <main className="app-shell app-shell-fallback">
          <section className="fallback-panel">
            <p className="eyebrow">Research Companion Agent</p>
            <h1>Frontend error</h1>
            <p className="intro">
              The app hit a runtime error while rendering. Refresh once after the backend is running, and if it still fails, check the browser console.
            </p>
            <pre className="fallback-error">{this.state.message}</pre>
          </section>
        </main>
      )
    }

    return this.props.children
  }
}

export default ErrorBoundary
