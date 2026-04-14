import { useNavigate } from 'react-router-dom'

/**
 * chatContext: optional object passed from the parent page.
 * It is merged into the /chat request body and used to pre-populate
 * the chat with the relevant log / airflow / k8s context.
 *
 * Shape examples:
 *   { log_text: "..." }                           ← log analysis page
 *   { airflow: { dag_id, dag_run_id, task_id } }  ← airflow page
 *   { k8s: { namespace, pod } }                   ← k8s pod logs
 */
export default function LogResultDisplay({ result, chatContext }) {
  const navigate = useNavigate()

  if (!result) return null

  const categoryColor = {
    Infrastructure: 'bg-orange-600',
    CodeLogic:      'bg-purple-600',
    DataQuality:    'bg-yellow-600',
    Unknown:        'bg-gray-600',
  }

  const goToChat = () => {
    const question =
      `I analyzed the logs and got: "${result.error_signature}". ` +
      `Root cause: ${result.suspected_root_cause}. ` +
      `Can you explain this in detail and what I should do next?`
    navigate('/', {
      state: {
        autoSend: true,
        question,
        mode: 'llm',
        ...chatContext,
      },
    })
  }

  return (
    <div className="mt-4 space-y-3 rounded border border-gray-700 bg-gray-800 p-4">
      <div className="flex flex-wrap items-center justify-between gap-2">
        <div className="flex flex-wrap items-center gap-2">
          <span className={`rounded px-2 py-0.5 text-xs font-semibold text-white ${categoryColor[result.category] || 'bg-gray-600'}`}>
            {result.category || 'Unknown'}
          </span>
          {result.confidence != null && (
            <span className="text-xs text-gray-400">Confidence: {(result.confidence * 100).toFixed(0)}%</span>
          )}
        </div>
        {/* Ask in Chat button — always visible after a result */}
        <button
          onClick={goToChat}
          className="rounded bg-indigo-600 px-3 py-1 text-xs font-medium text-white hover:bg-indigo-500"
        >
          Ask in Chat
        </button>
      </div>

      {result.error_signature && (
        <div>
          <h4 className="text-xs font-semibold text-gray-400">Error Signature</h4>
          <p className="font-mono text-sm text-gray-200">{result.error_signature}</p>
        </div>
      )}

      {result.summary && (
        <div>
          <h4 className="text-xs font-semibold text-gray-400">Summary</h4>
          <p className="text-sm text-gray-200">{result.summary}</p>
        </div>
      )}

      {result.suspected_root_cause && (
        <div>
          <h4 className="text-xs font-semibold text-gray-400">Suspected Root Cause</h4>
          <p className="text-sm text-gray-200">{result.suspected_root_cause}</p>
        </div>
      )}

      {result.next_actions?.length > 0 && (
        <div>
          <h4 className="text-xs font-semibold text-gray-400">Next Actions</h4>
          <ul className="ml-4 list-disc text-sm text-gray-200">
            {result.next_actions.map((a, i) => <li key={i}>{a}</li>)}
          </ul>
        </div>
      )}

      {result.evidence?.important_lines?.length > 0 && (
        <details className="text-xs">
          <summary className="cursor-pointer text-gray-400 hover:text-white">Show evidence lines</summary>
          <pre className="mt-1 overflow-x-auto rounded bg-gray-900 p-2 font-mono text-green-300 text-xs whitespace-pre-wrap">
            {result.evidence.important_lines.join('\n')}
          </pre>
        </details>
      )}
    </div>
  )
}
