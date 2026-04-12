export default function LogResultDisplay({ result }) {
  if (!result) return null

  const badgeColor = {
    error: 'bg-red-600',
    warning: 'bg-yellow-600',
    info: 'bg-blue-600',
    critical: 'bg-red-800',
  }

  return (
    <div className="mt-4 space-y-3 rounded border border-gray-700 bg-gray-800 p-4">
      <div className="flex flex-wrap items-center gap-2">
        <span
          className={`rounded px-2 py-0.5 text-xs font-semibold text-white ${badgeColor[result.category?.toLowerCase()] || 'bg-gray-600'}`}
        >
          {result.category || 'unknown'}
        </span>
        {result.confidence != null && (
          <span className="text-xs text-gray-400">
            Confidence: {(result.confidence * 100).toFixed(0)}%
          </span>
        )}
      </div>

      {result.error_signature && (
        <div>
          <h4 className="text-xs font-semibold text-gray-400">Error Signature</h4>
          <p className="font-mono text-sm text-gray-200">{result.error_signature}</p>
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
            {result.next_actions.map((a, i) => (
              <li key={i}>{a}</li>
            ))}
          </ul>
        </div>
      )}
    </div>
  )
}
