import { startTransition, useEffect, useState } from 'react'
import type { FormEvent } from 'react'
import './App.css'

type Message = {
  id: string
  role: 'user' | 'assistant'
  text: string
}

type ChatThread = {
  id: string
  title: string
  messages: Message[]
  createdAt: string
  updatedAt: string
}

const API_URL = import.meta.env.VITE_API_URL ?? 'http://localhost:3000'
const STORAGE_KEY = 'sports-analysis-chat-threads'
const ACTIVE_THREAD_KEY = 'sports-analysis-active-thread'

const examples = [
  'How did the Timberwolves perform against the Nuggets?',
  'Which teams struggled with three-point shooting in playoff games?',
  'Who looks strongest in the current NBA playoffs based on recent data?',
]

function createWelcomeMessage(): Message {
  return {
    id: crypto.randomUUID(),
    role: 'assistant',
    text: 'Ask a question about the NBA data you ingested into Pinecone.',
  }
}

function createThread(title = 'New chat'): ChatThread {
  const now = new Date().toISOString()
  return {
    id: crypto.randomUUID(),
    title,
    messages: [createWelcomeMessage()],
    createdAt: now,
    updatedAt: now,
  }
}

function isChatThread(value: unknown): value is ChatThread {
  if (!value || typeof value !== 'object') return false
  const candidate = value as ChatThread
  return (
    typeof candidate.id === 'string' &&
    typeof candidate.title === 'string' &&
    Array.isArray(candidate.messages) &&
    typeof candidate.createdAt === 'string' &&
    typeof candidate.updatedAt === 'string'
  )
}

function loadThreads(): ChatThread[] {
  if (typeof window === 'undefined') return [createThread()]

  try {
    const raw = window.localStorage.getItem(STORAGE_KEY)
    if (!raw) return [createThread()]

    const parsed = JSON.parse(raw)
    if (!Array.isArray(parsed)) return [createThread()]

    const threads = parsed.filter(isChatThread)
    return threads.length > 0 ? threads : [createThread()]
  } catch {
    return [createThread()]
  }
}

function loadActiveThreadId(threads: ChatThread[]): string {
  if (typeof window === 'undefined') return threads[0].id

  const stored = window.localStorage.getItem(ACTIVE_THREAD_KEY)
  return threads.some((thread) => thread.id === stored) ? (stored as string) : threads[0].id
}

function summarizeTitle(question: string): string {
  const trimmed = question.trim()
  if (trimmed.length <= 42) return trimmed
  return `${trimmed.slice(0, 39).trimEnd()}...`
}

function App() {
  const [threads, setThreads] = useState<ChatThread[]>(() => loadThreads())
  const [activeThreadId, setActiveThreadId] = useState<string>(() => loadActiveThreadId(loadThreads()))
  const [input, setInput] = useState('')
  const [isLoading, setIsLoading] = useState(false)
  const [error, setError] = useState('')
  const [editingThreadId, setEditingThreadId] = useState<string | null>(null)
  const [draftTitle, setDraftTitle] = useState('')

  const activeThread = threads.find((thread) => thread.id === activeThreadId) ?? threads[0]
  const canSend = input.trim().length > 0 && !isLoading

  useEffect(() => {
    window.localStorage.setItem(STORAGE_KEY, JSON.stringify(threads))
  }, [threads])

  useEffect(() => {
    if (!activeThread) return
    window.localStorage.setItem(ACTIVE_THREAD_KEY, activeThread.id)
  }, [activeThread])

  const updateThread = (threadId: string, updater: (thread: ChatThread) => ChatThread) => {
    startTransition(() => {
      setThreads((current) => current.map((thread) => (thread.id === threadId ? updater(thread) : thread)))
    })
  }

  const createNewThread = () => {
    const nextThread = createThread()
    setThreads((current) => [nextThread, ...current])
    setActiveThreadId(nextThread.id)
    setEditingThreadId(null)
    setDraftTitle('')
    setError('')
    setInput('')
  }

  const beginRenameThread = (thread: ChatThread) => {
    setEditingThreadId(thread.id)
    setDraftTitle(thread.title)
  }

  const commitRenameThread = (threadId: string) => {
    const nextTitle = draftTitle.trim() || 'New chat'
    updateThread(threadId, (thread) => ({
      ...thread,
      title: nextTitle,
      updatedAt: new Date().toISOString(),
    }))
    setEditingThreadId(null)
    setDraftTitle('')
  }

  const deleteThread = (threadId: string) => {
    setThreads((current) => {
      if (current.length === 1) {
        const freshThread = createThread()
        setActiveThreadId(freshThread.id)
        return [freshThread]
      }

      const remaining = current.filter((thread) => thread.id !== threadId)
      if (activeThreadId === threadId) {
        setActiveThreadId(remaining[0].id)
      }
      return remaining
    })
    setEditingThreadId(null)
    setDraftTitle('')
    setError('')
  }

  const sendMessage = async (prompt: string) => {
    const question = prompt.trim()
    if (!question || isLoading || !activeThread) return

    const assistantId = crypto.randomUUID()
    const threadId = activeThread.id
    const nextUpdatedAt = new Date().toISOString()

    setError('')
    setInput('')
    setIsLoading(true)
    updateThread(threadId, (thread) => ({
      ...thread,
      title: thread.title === 'New chat' ? summarizeTitle(question) : thread.title,
      updatedAt: nextUpdatedAt,
      messages: [
        ...thread.messages,
        { id: crypto.randomUUID(), role: 'user', text: question },
        { id: assistantId, role: 'assistant', text: '' },
      ],
    }))

    try {
      const response = await fetch(`${API_URL}/api/chat/`, {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ message: question, userId: 1 }),
      })

      if (!response.ok || !response.body) {
        throw new Error(`Chat request failed with status ${response.status}`)
      }

      const reader = response.body.getReader()
      const decoder = new TextDecoder()
      let buffer = ''

      while (true) {
        const { value, done } = await reader.read()
        if (done) break

        buffer += decoder.decode(value, { stream: true })
        const events = buffer.split('\n\n')
        buffer = events.pop() ?? ''

        for (const event of events) {
          const line = event
            .split('\n')
            .find((item) => item.startsWith('data: '))

          if (!line) continue

          const data = line.slice(6)
          if (data === '[DONE]') {
            setIsLoading(false)
            continue
          }

          const parsed = JSON.parse(data)
          if (parsed.error) {
            throw new Error(parsed.error)
          }

          if (parsed.text) {
            updateThread(threadId, (thread) => ({
              ...thread,
              updatedAt: new Date().toISOString(),
              messages: thread.messages.map((message) =>
                message.id === assistantId
                  ? { ...message, text: `${message.text}${parsed.text}` }
                  : message,
              ),
            }))
          }
        }
      }
    } catch (caught) {
      const message = caught instanceof Error ? caught.message : 'Something went wrong.'
      setError(message)
      updateThread(threadId, (thread) => ({
        ...thread,
        updatedAt: new Date().toISOString(),
        messages: thread.messages.map((message) =>
          message.id === assistantId
            ? { ...message, text: `I could not reach the chat endpoint. Check that FastAPI is running at ${API_URL}.` }
            : message,
        ),
      }))
    } finally {
      setIsLoading(false)
    }
  }

  const onSubmit = (event: FormEvent<HTMLFormElement>) => {
    event.preventDefault()
    void sendMessage(input)
  }

  return (
    <main className="app-shell">
      <section className="sidebar">
        <div className="sidebar-top">
          <div>
            <p className="eyebrow">Sports Analysis Agent</p>
            <h1>NBA data chat</h1>
            <p className="intro">
              Query your Pinecone index, compare teams, and keep separate chat threads for different lines of analysis.
            </p>
          </div>

          <div className="thread-panel">
            <div className="thread-panel-header">
              <p className="panel-label">Chats</p>
              <button className="new-thread-button" type="button" onClick={createNewThread}>
                New chat
              </button>
            </div>

            <div className="thread-list" aria-label="Chat threads">
              {threads.map((thread) => {
                const isActive = thread.id === activeThread.id
                const isEditing = thread.id === editingThreadId

                return (
                  <article
                    key={thread.id}
                    className={`thread-card${isActive ? ' active' : ''}`}
                    onClick={() => setActiveThreadId(thread.id)}
                  >
                    <div className="thread-card-main">
                      {isEditing ? (
                        <input
                          aria-label="Rename chat"
                          autoFocus
                          className="thread-title-input"
                          onBlur={() => commitRenameThread(thread.id)}
                          onChange={(event) => setDraftTitle(event.target.value)}
                          onKeyDown={(event) => {
                            if (event.key === 'Enter') {
                              event.preventDefault()
                              commitRenameThread(thread.id)
                            }
                            if (event.key === 'Escape') {
                              setEditingThreadId(null)
                              setDraftTitle('')
                            }
                          }}
                          value={draftTitle}
                        />
                      ) : (
                        <h2>{thread.title}</h2>
                      )}
                      <p>{thread.messages.filter((message) => message.role === 'user').length} prompts</p>
                    </div>

                    <div className="thread-card-actions">
                      <button
                        type="button"
                        onClick={(event) => {
                          event.stopPropagation()
                          beginRenameThread(thread)
                        }}
                      >
                        Rename
                      </button>
                      <button
                        type="button"
                        onClick={(event) => {
                          event.stopPropagation()
                          deleteThread(thread.id)
                        }}
                      >
                        Delete
                      </button>
                    </div>
                  </article>
                )
              })}
            </div>
          </div>

          <div className="examples">
            <p className="panel-label">Try one</p>
            {examples.map((example) => (
              <button key={example} className="example-button" type="button" onClick={() => void sendMessage(example)}>
                {example}
              </button>
            ))}
          </div>
        </div>

        <div className="status-panel">
          <span className="status-dot" />
          <span>{isLoading ? 'Thinking through retrieved records' : 'Ready for a new angle'}</span>
        </div>
      </section>

      <section className="chat-panel" aria-label="Chat">
        <div className="chat-panel-header">
          <div>
            <p className="panel-label">Active chat</p>
            <h2 className="chat-title">{activeThread.title}</h2>
          </div>
          <button className="secondary-action" type="button" onClick={() => beginRenameThread(activeThread)}>
            Rename chat
          </button>
        </div>

        <div className="messages">
          {activeThread.messages.map((message) => (
            <article className={`message ${message.role}`} key={message.id}>
              <span className="message-role">{message.role === 'user' ? 'You' : 'Analyst'}</span>
              <p>{message.text || '...'}</p>
            </article>
          ))}
        </div>

        {error && <p className="error-text">{error}</p>}

        <form className="composer" onSubmit={onSubmit}>
          <textarea
            aria-label="Ask a sports question"
            onChange={(event) => setInput(event.target.value)}
            placeholder="Ask about matchups, shooting, rebounds, playoff games..."
            rows={3}
            value={input}
          />
          <button disabled={!canSend} type="submit">
            {isLoading ? 'Running' : 'Send'}
          </button>
        </form>
      </section>
    </main>
  )
}

export default App
