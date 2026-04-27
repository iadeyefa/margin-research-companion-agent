import { useMemo, useState } from 'react'
import type { FormEvent } from 'react'
import './App.css'

type Message = {
  id: string
  role: 'user' | 'assistant'
  text: string
}

const API_URL = import.meta.env.VITE_API_URL ?? 'http://localhost:3000'

const examples = [
  'How did the Timberwolves perform against the Nuggets?',
  'Which teams struggled with three-point shooting in playoff games?',
  'Find games where a team won with strong rebounding and assists.',
]

function App() {
  const [input, setInput] = useState('')
  const [messages, setMessages] = useState<Message[]>([
    {
      id: 'welcome',
      role: 'assistant',
      text: 'Ask a question about the NBA data you ingested into Pinecone.',
    },
  ])
  const [isLoading, setIsLoading] = useState(false)
  const [error, setError] = useState('')

  const canSend = useMemo(() => input.trim().length > 0 && !isLoading, [input, isLoading])

  const sendMessage = async (prompt: string) => {
    const question = prompt.trim()
    if (!question || isLoading) return

    const assistantId = crypto.randomUUID()
    setError('')
    setInput('')
    setIsLoading(true)
    setMessages((current) => [
      ...current,
      { id: crypto.randomUUID(), role: 'user', text: question },
      { id: assistantId, role: 'assistant', text: '' },
    ])

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
            setMessages((current) =>
              current.map((message) =>
                message.id === assistantId
                  ? { ...message, text: `${message.text}${parsed.text}` }
                  : message,
              ),
            )
          }
        }
      }
    } catch (caught) {
      const message = caught instanceof Error ? caught.message : 'Something went wrong.'
      setError(message)
      setMessages((current) =>
        current.map((item) =>
          item.id === assistantId
            ? { ...item, text: `I could not reach the chat endpoint. Check that FastAPI is running at ${API_URL}.` }
            : item,
        ),
      )
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
        <div>
          <p className="eyebrow">Sports Analysis Agent</p>
          <h1>NBA data chat</h1>
          <p className="intro">
            Query your Pinecone index using semantic search over team box-score records.
          </p>
        </div>

        <div className="examples">
          <p className="panel-label">Try one</p>
          {examples.map((example) => (
            <button key={example} className="example-button" type="button" onClick={() => void sendMessage(example)}>
              {example}
            </button>
          ))}
        </div>

        <div className="status-panel">
          <span className="status-dot" />
          <span>{isLoading ? 'Thinking through retrieved records' : 'Connected to FastAPI'}</span>
        </div>
      </section>

      <section className="chat-panel" aria-label="Chat">
        <div className="messages">
          {messages.map((message) => (
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
