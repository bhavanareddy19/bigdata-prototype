import { useState, useRef, useEffect } from 'react'
import ModeSelector from '../components/ModeSelector'

export default function ChatPage() {
  const [messages, setMessages] = useState([])
  const [input, setInput] = useState('')
  const [mode, setMode] = useState('auto')
  const [loading, setLoading] = useState(false)
  const [error, setError] = useState(null)
  const bottomRef = useRef(null)

  useEffect(() => {
    bottomRef.current?.scrollIntoView({ behavior: 'smooth' })
  }, [messages])

  const history = messages
    .map((m) => (m.role === 'user' ? { role: 'user', content: m.text } : { role: 'assistant', content: m.text }))

  const send = async () => {
    const q = input.trim()
    if (!q || loading) return

    setInput('')
    setError(null)
    const userMsg = { role: 'user', text: q }
    setMessages((prev) => [...prev, userMsg])
    setLoading(true)

    try {
      const res = await fetch('/chat', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ question: q, history, mode }),
      })
      if (!res.ok) throw new Error(`${res.status} ${res.statusText}`)
      const data = await res.json()
      setMessages((prev) => [
        ...prev,
        { role: 'assistant', text: data.answer, sources: data.sources },
      ])
    } catch (e) {
      setError(e.message)
    } finally {
      setLoading(false)
    }
  }

  const handleKey = (e) => {
    if (e.key === 'Enter' && !e.shiftKey) {
      e.preventDefault()
      send()
    }
  }

  return (
    <div className="flex h-full flex-col">
      <div className="mb-4 flex items-center gap-3">
        <h1 className="text-xl font-bold text-white">Chat</h1>
        <ModeSelector value={mode} onChange={setMode} />
      </div>

      <div className="flex-1 space-y-4 overflow-y-auto pr-2">
        {messages.map((m, i) => (
          <div key={i} className={`flex ${m.role === 'user' ? 'justify-end' : 'justify-start'}`}>
            <div
              className={`max-w-[75%] rounded-lg px-4 py-2 text-sm ${
                m.role === 'user'
                  ? 'bg-blue-600 text-white'
                  : 'bg-gray-800 text-gray-200'
              }`}
            >
              <p className="whitespace-pre-wrap">{m.text}</p>
              {m.sources?.length > 0 && <SourcesSection sources={m.sources} />}
            </div>
          </div>
        ))}
        {loading && (
          <div className="flex justify-start">
            <div className="rounded-lg bg-gray-800 px-4 py-2 text-sm text-gray-400">
              Thinking...
            </div>
          </div>
        )}
        <div ref={bottomRef} />
      </div>

      {error && <p className="mt-2 text-sm text-red-400">{error}</p>}

      <div className="mt-4 flex gap-2">
        <input
          value={input}
          onChange={(e) => setInput(e.target.value)}
          onKeyDown={handleKey}
          placeholder="Ask a question..."
          className="flex-1 rounded border border-gray-600 bg-gray-800 px-4 py-2 text-sm text-gray-200 placeholder-gray-500 focus:border-blue-500 focus:outline-none"
        />
        <button
          onClick={send}
          disabled={loading || !input.trim()}
          className="rounded bg-blue-600 px-5 py-2 text-sm font-medium text-white hover:bg-blue-700 disabled:opacity-50"
        >
          Send
        </button>
      </div>
    </div>
  )
}

function SourcesSection({ sources }) {
  const [open, setOpen] = useState(false)

  return (
    <div className="mt-2 border-t border-gray-700 pt-2">
      <button
        onClick={() => setOpen(!open)}
        className="text-xs font-medium text-blue-400 hover:text-blue-300"
      >
        {open ? 'Hide' : 'Show'} Sources ({sources.length})
      </button>
      {open && (
        <div className="mt-2 space-y-2">
          {sources.map((s, i) => (
            <div key={i} className="rounded bg-gray-900 p-2 text-xs">
              <p className="font-mono text-gray-400">{s.source || s.path}</p>
              {s.snippet && <p className="mt-1 text-gray-300">{s.snippet}</p>}
              {s.relevance_score != null && (
                <p className="mt-1 text-gray-500">Relevance: {(s.relevance_score * 100).toFixed(0)}%</p>
              )}
            </div>
          ))}
        </div>
      )}
    </div>
  )
}
