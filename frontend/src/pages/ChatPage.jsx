import { useState, useRef, useEffect, useCallback } from 'react'
import { useLocation } from 'react-router-dom'
import ReactMarkdown from 'react-markdown'
import ModeSelector from '../components/ModeSelector'

export default function ChatPage() {
  const [messages, setMessages] = useState([])
  const [input, setInput] = useState('')
  const [mode, setMode] = useState('auto')
  const [loading, setLoading] = useState(false)
  const [error, setError] = useState(null)
  const bottomRef = useRef(null)
  const autoSentRef = useRef(false)
  const location = useLocation()

  useEffect(() => {
    bottomRef.current?.scrollIntoView({ behavior: 'smooth' })
  }, [messages])

  // Core send — accepts optional extra payload (log_text, k8s_diagnose, airflow)
  const sendMessage = useCallback(async (question, extra = {}) => {
    if (!question.trim() || loading) return
    setError(null)
    const userMsg = { role: 'user', text: question }
    setMessages((prev) => [...prev, userMsg])
    setLoading(true)
    try {
      const history = messages.map((m) => ({ role: m.role, content: m.text }))
      const body = { question, history, mode, ...extra }
      const res = await fetch('/chat', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify(body),
      })
      if (!res.ok) {
        const err = await res.json().catch(() => ({}))
        throw new Error(err.detail || `${res.status} ${res.statusText}`)
      }
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
  }, [loading, messages, mode])

  // Auto-send when navigated here from another page with context
  useEffect(() => {
    const state = location.state
    if (!state?.autoSend || autoSentRef.current) return
    autoSentRef.current = true
    window.history.replaceState({}, '') // clear state so back-nav doesn't retrigger

    const { question, ...extra } = state
    delete extra.autoSend
    setInput('')
    sendMessage(question, extra)
  }, []) // only on mount

  const send = () => {
    const q = input.trim()
    if (!q) return
    setInput('')
    sendMessage(q)
  }

  const handleKey = (e) => {
    if (e.key === 'Enter' && !e.shiftKey) { e.preventDefault(); send() }
  }

  return (
    <div className="flex h-full flex-col">
      <div className="mb-4 flex items-center gap-3">
        <h1 className="text-xl font-bold text-white">Chat</h1>
        <ModeSelector value={mode} onChange={setMode} />
      </div>

      <div className="flex-1 space-y-4 overflow-y-auto pr-2">
        {messages.length === 0 && !loading && (
          <div className="text-sm text-gray-500 space-y-1">
            <p>Ask anything about your pipelines, pods, or logs.</p>
            <p className="text-xs">Examples:</p>
            <ul className="list-disc pl-4 text-xs space-y-0.5">
              <li>Why is the <strong className="text-gray-400">data_ingestion</strong> dag failing?</li>
              <li>Are all my <strong className="text-gray-400">Kubernetes pods</strong> healthy?</li>
              <li>What does <strong className="text-gray-400">CrashLoopBackOff</strong> mean?</li>
              <li>Explain the <strong className="text-gray-400">ml_pipeline</strong> dag</li>
            </ul>
          </div>
        )}

        {messages.map((m, i) => (
          <div key={i} className={`flex ${m.role === 'user' ? 'justify-end' : 'justify-start'}`}>
            <div
              className={`max-w-[78%] rounded-lg px-4 py-3 text-sm ${
                m.role === 'user' ? 'bg-blue-600 text-white' : 'bg-gray-800 text-gray-200'
              }`}
            >
              {m.role === 'assistant' ? (
                <MarkdownMessage text={m.text} />
              ) : (
                <p className="whitespace-pre-wrap">{m.text}</p>
              )}
              {m.sources?.length > 0 && <SourcesSection sources={m.sources} />}
            </div>
          </div>
        ))}

        {loading && (
          <div className="flex justify-start">
            <div className="rounded-lg bg-gray-800 px-4 py-2 text-sm text-gray-400 animate-pulse">
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
          placeholder="Ask about pipelines, K8s pods, errors..."
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

function MarkdownMessage({ text }) {
  return (
    <div className="prose prose-invert prose-sm max-w-none">
      <ReactMarkdown
        components={{
          p:      ({ children }) => <p className="mb-2 last:mb-0">{children}</p>,
          ul:     ({ children }) => <ul className="mb-2 list-disc pl-5">{children}</ul>,
          ol:     ({ children }) => <ol className="mb-2 list-decimal pl-5">{children}</ol>,
          li:     ({ children }) => <li className="mb-0.5">{children}</li>,
          strong: ({ children }) => <strong className="font-semibold text-white">{children}</strong>,
          code:   ({ node, className, children, ...props }) => {
            // react-markdown v7+ removed the `inline` prop — detect by newlines or language class
            const isBlock = className || String(children).includes('\n')
            return isBlock
              ? <pre className="my-2 overflow-x-auto rounded bg-gray-900 p-3 font-mono text-xs text-green-300 whitespace-pre-wrap"><code>{children}</code></pre>
              : <code className="rounded bg-gray-900 px-1.5 py-0.5 font-mono text-xs text-green-300 inline">{children}</code>
          },
          h1: ({ children }) => <h1 className="mb-2 text-base font-bold text-white">{children}</h1>,
          h2: ({ children }) => <h2 className="mb-1 text-sm font-bold text-white">{children}</h2>,
          h3: ({ children }) => <h3 className="mb-1 text-sm font-semibold text-gray-100">{children}</h3>,
        }}
      >
        {text}
      </ReactMarkdown>
    </div>
  )
}

function SourcesSection({ sources }) {
  const [open, setOpen] = useState(false)
  return (
    <div className="mt-2 border-t border-gray-700 pt-2">
      <button onClick={() => setOpen(!open)} className="text-xs font-medium text-blue-400 hover:text-blue-300">
        {open ? 'Hide' : 'Show'} Sources ({sources.length})
      </button>
      {open && (
        <div className="mt-2 space-y-2">
          {sources.map((s, i) => (
            <div key={i} className="rounded bg-gray-900 p-2 text-xs">
              <p className="font-mono text-gray-400">{s.source || s.path}</p>
              {s.snippet && <p className="mt-1 text-gray-300">{s.snippet}</p>}
              {s.relevance != null && <p className="mt-1 text-gray-500">Relevance: {s.relevance}</p>}
            </div>
          ))}
        </div>
      )}
    </div>
  )
}
