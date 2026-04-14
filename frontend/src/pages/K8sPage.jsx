import { useEffect, useState } from 'react'
import { useNavigate } from 'react-router-dom'
import ReactMarkdown from 'react-markdown'
import ModeSelector from '../components/ModeSelector'
import LogResultDisplay from '../components/LogResultDisplay'

export default function K8sPage() {
  const [tab, setTab] = useState('diagnose')
  const [namespaces, setNamespaces] = useState([])
  const [namespace, setNamespace] = useState('backend')
  const [loadingNs, setLoadingNs] = useState(false)

  useEffect(() => {
    ;(async () => {
      try {
        setLoadingNs(true)
        const res = await fetch('/k8s/namespaces')
        if (!res.ok) throw new Error(`${res.status}`)
        const data = await res.json()
        setNamespaces(data.namespaces || [])
      } catch { /* cluster may not be reachable in dev */ }
      finally { setLoadingNs(false) }
    })()
  }, [])

  return (
    <div>
      <div className="mb-4 flex items-center gap-4">
        <h1 className="text-xl font-bold text-white">Kubernetes</h1>
        <div className="flex gap-2">
          <button
            onClick={() => setTab('diagnose')}
            className={`rounded px-3 py-1 text-sm ${tab === 'diagnose' ? 'bg-blue-600 text-white' : 'bg-gray-700 text-gray-300'}`}
          >Diagnose</button>
          <button
            onClick={() => setTab('logs')}
            className={`rounded px-3 py-1 text-sm ${tab === 'logs' ? 'bg-blue-600 text-white' : 'bg-gray-700 text-gray-300'}`}
          >Pod Logs</button>
        </div>
      </div>

      <div className="mb-4">
        <label className="mr-2 text-sm text-gray-400">Namespace:</label>
        {namespaces.length > 0 ? (
          <select
            value={namespace}
            onChange={(e) => setNamespace(e.target.value)}
            className="rounded border border-gray-600 bg-gray-800 px-3 py-1 text-sm text-gray-200"
          >
            {namespaces.map((n) => <option key={n} value={n}>{n}</option>)}
          </select>
        ) : (
          <input
            value={namespace}
            onChange={(e) => setNamespace(e.target.value)}
            placeholder={loadingNs ? 'loading…' : 'Namespace'}
            className="rounded border border-gray-600 bg-gray-800 px-3 py-1 text-sm text-gray-200"
          />
        )}
      </div>

      {tab === 'diagnose' ? <DiagnosePanel namespace={namespace} /> : <LogsPanel namespace={namespace} />}
    </div>
  )
}

function DiagnosePanel({ namespace }) {
  const navigate = useNavigate()
  const [loading, setLoading] = useState(false)
  const [diag, setDiag] = useState(null)
  const [error, setError] = useState(null)
  const [aiAnswer, setAiAnswer] = useState(null)
  const [asking, setAsking] = useState(false)

  const run = async () => {
    if (!namespace.trim() || loading) return
    setLoading(true); setError(null); setDiag(null); setAiAnswer(null)
    try {
      const res = await fetch(`/k8s/diagnose/${encodeURIComponent(namespace)}`)
      if (!res.ok) {
        const body = await res.json().catch(() => ({}))
        throw new Error(body.detail || `${res.status} ${res.statusText}`)
      }
      setDiag(await res.json())
    } catch (e) { setError(e.message) }
    finally { setLoading(false) }
  }

  const askAI = async () => {
    if (!diag || asking) return
    setAsking(true); setAiAnswer(null)
    try {
      const res = await fetch('/chat', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({
          question: `Analyze the Kubernetes problems in namespace "${namespace}". For each problem pod, explain clearly: 1) what the error means, 2) the most likely root cause, 3) what to check next. Be specific and concise.`,
          k8s_diagnose: { namespace },
          include_repo_context: false,
          mode: 'llm',
        }),
      })
      if (!res.ok) {
        const body = await res.json().catch(() => ({}))
        throw new Error(body.detail || `${res.status} ${res.statusText}`)
      }
      setAiAnswer(await res.json())
    } catch (e) { setError(e.message) }
    finally { setAsking(false) }
  }

  return (
    <div>
      <div className="flex gap-2">
        <button onClick={run} disabled={loading}
          className="rounded bg-blue-600 px-5 py-2 text-sm font-medium text-white hover:bg-blue-700 disabled:opacity-50">
          {loading ? 'Scanning…' : 'Scan Namespace'}
        </button>
        <button onClick={askAI} disabled={!diag || asking}
          className="rounded bg-purple-600 px-5 py-2 text-sm font-medium text-white hover:bg-purple-700 disabled:opacity-50">
          {asking ? 'Thinking…' : 'Diagnose with AI'}
        </button>
      </div>

      {error && (
        /503|unreachable|not reachable|ECONNREFUSED|refused/i.test(error)
          ? (
            <div className="mt-4 rounded border border-yellow-600 bg-gray-800 p-4 text-sm">
              <p className="font-semibold text-yellow-300">No Kubernetes cluster connected</p>
              <p className="mt-1 text-gray-300">
                To use this feature, either:
              </p>
              <ul className="mt-2 list-disc pl-5 text-gray-300 space-y-1">
                <li>Enable Kubernetes in Docker Desktop (Settings → Kubernetes → Enable Kubernetes)</li>
                <li>Deploy to GKE and ensure the backend pod has cluster RBAC access</li>
                <li>Set a valid kubeconfig that points to your cluster</li>
              </ul>
              <p className="mt-2 text-gray-400 text-xs">You can still ask general Kubernetes questions in the Chat tab.</p>
            </div>
          )
          : <p className="mt-3 text-sm text-red-400">{error}</p>
      )}

      {diag && (
        <div className="mt-4 space-y-3 text-sm">
          <div className="rounded bg-gray-800 p-3">
            <div className="text-gray-300">
              <strong>{diag.namespace}</strong> — {diag.pod_count} pods, {diag.problem_pod_count} with problems
              {diag.healthy && <span className="ml-2 text-green-400">✓ healthy</span>}
            </div>
          </div>

          {diag.problems?.length > 0 && (
            <div className="rounded bg-gray-800 p-3">
              <h3 className="mb-2 font-semibold text-red-300">Problem pods</h3>
              <table className="w-full text-xs">
                <thead><tr className="text-gray-400">
                  <th className="text-left">Pod</th><th>Phase</th><th>Ready</th><th>Restarts</th><th>Reasons</th>
                </tr></thead>
                <tbody>
                  {diag.problems.map((p) => (
                    <tr key={p.pod} className="border-t border-gray-700 text-gray-200">
                      <td className="py-1 font-mono">{p.pod}</td>
                      <td className="text-center">{p.phase}</td>
                      <td className="text-center">{p.ready}</td>
                      <td className="text-center">{p.restarts}</td>
                      <td>{p.reasons.join(', ')}</td>
                    </tr>
                  ))}
                </tbody>
              </table>
            </div>
          )}

          {diag.remediation_hints?.length > 0 && (
            <div className="rounded bg-gray-800 p-3">
              <h3 className="mb-2 font-semibold text-yellow-300">Remediation hints</h3>
              <ul className="list-disc pl-5 text-gray-200">
                {diag.remediation_hints.map((h) => (
                  <li key={h.reason}><strong>{h.reason}:</strong> {h.action}</li>
                ))}
              </ul>
            </div>
          )}

          {diag.warning_events?.length > 0 && (
            <div className="rounded bg-gray-800 p-3">
              <h3 className="mb-2 font-semibold text-orange-300">Warning events</h3>
              <ul className="text-xs text-gray-200">
                {diag.warning_events.map((e, i) => (
                  <li key={i} className="py-0.5">
                    <span className="text-orange-400">{e.reason}</span> on {e.object} (×{e.count}): {e.message}
                  </li>
                ))}
              </ul>
            </div>
          )}
        </div>
      )}

      {aiAnswer && (
        <div className="mt-4 rounded border border-purple-700 bg-gray-800 p-4 text-sm text-gray-200">
          <div className="mb-2 flex items-center justify-between">
            <h3 className="font-semibold text-purple-300">AI Diagnosis</h3>
            <button
              onClick={() => navigate('/', { state: { autoSend: true, question: `Tell me more about the Kubernetes problems in namespace "${namespace}" and how I should resolve them step by step.`, k8s_diagnose: { namespace }, mode: 'llm' } })}
              className="rounded bg-indigo-600 px-3 py-1 text-xs text-white hover:bg-indigo-500"
            >
              Continue in Chat
            </button>
          </div>
          <div className="prose prose-invert prose-sm max-w-none">
            <ReactMarkdown>{aiAnswer.answer}</ReactMarkdown>
          </div>
        </div>
      )}
    </div>
  )
}

function LogsPanel({ namespace }) {
  const [podName, setPodName] = useState('')
  const [container, setContainer] = useState('')
  const [tailLines, setTailLines] = useState('500')
  const [mode, setMode] = useState('auto')
  const [loading, setLoading] = useState(false)
  const [result, setResult] = useState(null)
  const [error, setError] = useState(null)
  const [pods, setPods] = useState([])

  useEffect(() => {
    if (!namespace) return
    ;(async () => {
      try {
        const res = await fetch(`/k8s/pods/${encodeURIComponent(namespace)}`)
        if (res.ok) setPods((await res.json()).pods || [])
      } catch { /* ignore */ }
    })()
  }, [namespace])

  const submit = async () => {
    if (!namespace.trim() || !podName.trim() || loading) return
    setLoading(true); setError(null); setResult(null)
    try {
      const body = {
        namespace,
        pod: podName,
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
    } catch (e) { setError(e.message) }
    finally { setLoading(false) }
  }

  const inputCls =
    'rounded border border-gray-600 bg-gray-800 px-3 py-2 text-sm text-gray-200 placeholder-gray-500 focus:border-blue-500 focus:outline-none'

  return (
    <div>
      <div className="mb-3 flex items-center gap-3">
        <ModeSelector value={mode} onChange={setMode} />
      </div>

      <div className="grid grid-cols-2 gap-3">
        {pods.length > 0 ? (
          <select value={podName} onChange={(e) => setPodName(e.target.value)} className={inputCls}>
            <option value="">— Select pod —</option>
            {pods.map((p) => (
              <option key={p.name} value={p.name}>
                {p.name} ({p.phase}, restarts={p.restarts})
              </option>
            ))}
          </select>
        ) : (
          <input value={podName} onChange={(e) => setPodName(e.target.value)} placeholder="Pod Name" className={inputCls} />
        )}
        <input value={container} onChange={(e) => setContainer(e.target.value)} placeholder="Container (optional)" className={inputCls} />
        <input value={tailLines} onChange={(e) => setTailLines(e.target.value)} placeholder="Tail Lines" type="number" min="1" className={inputCls} />
      </div>

      <button
        onClick={submit}
        disabled={loading || !namespace.trim() || !podName.trim()}
        className="mt-3 rounded bg-blue-600 px-5 py-2 text-sm font-medium text-white hover:bg-blue-700 disabled:opacity-50"
      >
        {loading ? 'Analyzing…' : 'Analyze'}
      </button>

      {error && <p className="mt-3 text-sm text-red-400">{error}</p>}
      <LogResultDisplay
        result={result}
        chatContext={{ k8s: { namespace, pod: podName, container: container || undefined, tail_lines: parseInt(tailLines,10)||500, timestamps: true } }}
      />
    </div>
  )
}
