import { useState } from 'react'
import ModeSelector from '../components/ModeSelector'
import LogResultDisplay from '../components/LogResultDisplay'

export default function LogAnalysisPage() {
  const [logText, setLogText] = useState('')
  const [mode, setMode] = useState('auto')
  const [loading, setLoading] = useState(false)
  const [result, setResult] = useState(null)
  const [error, setError] = useState(null)

  const submit = async () => {
    if (!logText.trim() || loading) return
    setLoading(true)
    setError(null)
    setResult(null)
    try {
      const res = await fetch('/analyze-log', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ log_text: logText, mode }),
      })
      if (!res.ok) throw new Error(`${res.status} ${res.statusText}`)
      setResult(await res.json())
    } catch (e) {
      setError(e.message)
    } finally {
      setLoading(false)
    }
  }

  return (
    <div>
      <div className="mb-4 flex items-center gap-3">
        <h1 className="text-xl font-bold text-white">Log Analysis</h1>
        <ModeSelector value={mode} onChange={setMode} />
      </div>

      <textarea
        value={logText}
        onChange={(e) => setLogText(e.target.value)}
        placeholder="Paste raw log text here..."
        rows={10}
        className="w-full rounded border border-gray-600 bg-gray-800 p-3 font-mono text-sm text-gray-200 placeholder-gray-500 focus:border-blue-500 focus:outline-none"
      />

      <button
        onClick={submit}
        disabled={loading || !logText.trim()}
        className="mt-3 rounded bg-blue-600 px-5 py-2 text-sm font-medium text-white hover:bg-blue-700 disabled:opacity-50"
      >
        {loading ? 'Analyzing...' : 'Analyze'}
      </button>

      {error && <p className="mt-3 text-sm text-red-400">{error}</p>}
      <LogResultDisplay result={result} chatContext={{ log_text: logText }} />
    </div>
  )
}
