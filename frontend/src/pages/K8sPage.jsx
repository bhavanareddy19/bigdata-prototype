import { useState } from 'react'
import ModeSelector from '../components/ModeSelector'
import LogResultDisplay from '../components/LogResultDisplay'

export default function K8sPage() {
  const [namespace, setNamespace] = useState('')
  const [podName, setPodName] = useState('')
  const [container, setContainer] = useState('')
  const [tailLines, setTailLines] = useState('500')
  const [mode, setMode] = useState('auto')
  const [loading, setLoading] = useState(false)
  const [result, setResult] = useState(null)
  const [error, setError] = useState(null)

  const submit = async () => {
    if (!namespace.trim() || !podName.trim() || loading) return
    setLoading(true)
    setError(null)
    setResult(null)
    try {
      const body = {
        namespace,
        pod_name: podName,
        tail_lines: parseInt(tailLines, 10) || 500,
        mode,
      }
      if (container.trim()) body.container = container
      const res = await fetch('/analyze-k8s-pod', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify(body),
      })
      if (!res.ok) throw new Error(`${res.status} ${res.statusText}`)
      setResult(await res.json())
    } catch (e) {
      setError(e.message)
    } finally {
      setLoading(false)
    }
  }

  const inputCls =
    'rounded border border-gray-600 bg-gray-800 px-3 py-2 text-sm text-gray-200 placeholder-gray-500 focus:border-blue-500 focus:outline-none'

  return (
    <div>
      <div className="mb-4 flex items-center gap-3">
        <h1 className="text-xl font-bold text-white">Kubernetes Pod Logs</h1>
        <ModeSelector value={mode} onChange={setMode} />
      </div>

      <div className="grid grid-cols-2 gap-3">
        <input value={namespace} onChange={(e) => setNamespace(e.target.value)} placeholder="Namespace" className={inputCls} />
        <input value={podName} onChange={(e) => setPodName(e.target.value)} placeholder="Pod Name" className={inputCls} />
        <input value={container} onChange={(e) => setContainer(e.target.value)} placeholder="Container (optional)" className={inputCls} />
        <input value={tailLines} onChange={(e) => setTailLines(e.target.value)} placeholder="Tail Lines" type="number" min="1" className={inputCls} />
      </div>

      <button
        onClick={submit}
        disabled={loading || !namespace.trim() || !podName.trim()}
        className="mt-3 rounded bg-blue-600 px-5 py-2 text-sm font-medium text-white hover:bg-blue-700 disabled:opacity-50"
      >
        {loading ? 'Analyzing...' : 'Analyze'}
      </button>

      {error && <p className="mt-3 text-sm text-red-400">{error}</p>}
      <LogResultDisplay result={result} />
    </div>
  )
}
