import { useState, useEffect } from 'react'
import ModeSelector from '../components/ModeSelector'
import LogResultDisplay from '../components/LogResultDisplay'

export default function AirflowPage() {
  const [dagId, setDagId]       = useState('')
  const [dagRunId, setDagRunId] = useState('')
  const [taskId, setTaskId]     = useState('')
  const [tryNumber, setTryNumber] = useState('1')
  // Leave baseUrl empty — backend uses its own AIRFLOW_BASE_URL env var
  const [baseUrl, setBaseUrl]   = useState('')
  const [mode, setMode]         = useState('auto')
  const [loading, setLoading]   = useState(false)
  const [result, setResult]     = useState(null)
  const [error, setError]       = useState(null)
  const [failures, setFailures] = useState([])

  // Load recent failures so user can click to fill in the form
  useEffect(() => {
    ;(async () => {
      try {
        const res = await fetch('/ops/latest-failures')
        if (!res.ok) return
        const data = await res.json()
        setFailures(data.recent_failures || [])
      } catch { /* ignore */ }
    })()
  }, [])

  const fillFromFailure = (f) => {
    // Guard: task_id should not look like a dag_run_id (scheduled__... / manual__...)
    const rawTaskId = f.task_id || ''
    const safeTaskId = /^(scheduled__|manual__|backfill_)/.test(rawTaskId) ? '' : rawTaskId
    setDagId(f.dag_id || '')
    setDagRunId(f.dag_run_id || '')
    setTaskId(safeTaskId)
    setTryNumber(String(f.try_number || 1))
    setResult(null)
    setError(null)
  }

  const submit = async () => {
    if (!dagId.trim() || !dagRunId.trim() || !taskId.trim() || loading) return
    setLoading(true)
    setError(null)
    setResult(null)
    try {
      const body = {
        dag_id: dagId,
        dag_run_id: dagRunId,
        task_id: taskId,
        try_number: parseInt(tryNumber, 10) || 1,
        mode,
      }
      // Only send base URL if user explicitly typed one
      if (baseUrl.trim()) body.airflow_base_url = baseUrl.trim()

      const res = await fetch('/analyze-airflow-task', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify(body),
      })
      if (!res.ok) {
        const err = await res.json().catch(() => ({}))
        throw new Error(err.detail || `${res.status} ${res.statusText}`)
      }
      setResult(await res.json())
    } catch (e) {
      setError(e.message)
    } finally {
      setLoading(false)
    }
  }

  const inputCls =
    'rounded border border-gray-600 bg-gray-800 px-3 py-2 text-sm text-gray-200 placeholder-gray-500 focus:border-blue-500 focus:outline-none w-full'

  return (
    <div>
      <div className="mb-4 flex items-center gap-3">
        <h1 className="text-xl font-bold text-white">Airflow Task Logs</h1>
        <ModeSelector value={mode} onChange={setMode} />
      </div>

      {/* Recent failures — click to auto-fill form */}
      {failures.length > 0 && (
        <div className="mb-4 rounded border border-gray-700 bg-gray-800 p-3">
          <p className="mb-2 text-xs font-semibold text-gray-400 uppercase tracking-wider">Recent Failures — click to load</p>
          <div className="flex flex-wrap gap-2">
            {failures.map((f, i) => (
              <button
                key={i}
                onClick={() => fillFromFailure(f)}
                className="rounded bg-red-900 px-2 py-1 text-xs text-red-200 hover:bg-red-800"
              >
                {f.dag_id} / {f.task_id} (try {f.try_number})
              </button>
            ))}
          </div>
        </div>
      )}

      <div className="grid grid-cols-2 gap-3">
        <input value={dagId}    onChange={(e) => setDagId(e.target.value)}    placeholder="DAG ID" className={inputCls} />
        <input value={dagRunId} onChange={(e) => setDagRunId(e.target.value)} placeholder="DAG Run ID (e.g. scheduled__2026-04-12T00:00:00+00:00)" className={inputCls} />
        <input value={taskId}   onChange={(e) => setTaskId(e.target.value)}   placeholder="Task ID" className={inputCls} />
        <input
          value={tryNumber}
          onChange={(e) => setTryNumber(e.target.value)}
          placeholder="Try Number (1 = first run, 2 = first retry…)"
          type="number" min="1"
          className={inputCls}
        />
        <input
          value={baseUrl}
          onChange={(e) => setBaseUrl(e.target.value)}
          placeholder="Airflow Base URL (leave blank to use server default)"
          className={`${inputCls} col-span-2`}
        />
      </div>

      <button
        onClick={submit}
        disabled={loading || !dagId.trim() || !dagRunId.trim() || !taskId.trim()}
        className="mt-3 rounded bg-blue-600 px-5 py-2 text-sm font-medium text-white hover:bg-blue-700 disabled:opacity-50"
      >
        {loading ? 'Analyzing...' : 'Analyze'}
      </button>

      {error && <p className="mt-3 text-sm text-red-400">{error}</p>}
      <LogResultDisplay
        result={result}
        chatContext={{
          airflow: {
            dag_id: dagId,
            dag_run_id: dagRunId,
            task_id: taskId,
            try_number: parseInt(tryNumber, 10) || 1,
            max_lines: 250,
          },
        }}
      />
    </div>
  )
}
