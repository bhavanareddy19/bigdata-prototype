import { useState } from 'react'
import ModeSelector from '../components/ModeSelector'
import LogResultDisplay from '../components/LogResultDisplay'

export default function AirflowPage() {
  const [dagId, setDagId] = useState('')
  const [dagRunId, setDagRunId] = useState('')
  const [taskId, setTaskId] = useState('')
  const [tryNumber, setTryNumber] = useState('1')
  const [baseUrl, setBaseUrl] = useState('http://localhost:8080')
  const [mode, setMode] = useState('auto')
  const [loading, setLoading] = useState(false)
  const [result, setResult] = useState(null)
  const [error, setError] = useState(null)

  const submit = async () => {
    if (!dagId.trim() || !dagRunId.trim() || !taskId.trim() || loading) return
    setLoading(true)
    setError(null)
    setResult(null)
    try {
      const res = await fetch('/analyze-airflow-task', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({
          dag_id: dagId,
          dag_run_id: dagRunId,
          task_id: taskId,
          try_number: parseInt(tryNumber, 10) || 1,
          airflow_base_url: baseUrl,
          mode,
        }),
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
        <h1 className="text-xl font-bold text-white">Airflow Task Logs</h1>
        <ModeSelector value={mode} onChange={setMode} />
      </div>

      <div className="grid grid-cols-2 gap-3">
        <input value={dagId} onChange={(e) => setDagId(e.target.value)} placeholder="DAG ID" className={inputCls} />
        <input value={dagRunId} onChange={(e) => setDagRunId(e.target.value)} placeholder="DAG Run ID" className={inputCls} />
        <input value={taskId} onChange={(e) => setTaskId(e.target.value)} placeholder="Task ID" className={inputCls} />
        <input value={tryNumber} onChange={(e) => setTryNumber(e.target.value)} placeholder="Try Number" type="number" min="1" className={inputCls} />
        <input value={baseUrl} onChange={(e) => setBaseUrl(e.target.value)} placeholder="Airflow Base URL" className={`${inputCls} col-span-2`} />
      </div>

      <button
        onClick={submit}
        disabled={loading || !dagId.trim() || !dagRunId.trim() || !taskId.trim()}
        className="mt-3 rounded bg-blue-600 px-5 py-2 text-sm font-medium text-white hover:bg-blue-700 disabled:opacity-50"
      >
        {loading ? 'Analyzing...' : 'Analyze'}
      </button>

      {error && <p className="mt-3 text-sm text-red-400">{error}</p>}
      <LogResultDisplay result={result} />
    </div>
  )
}
