import { useState, useEffect, useCallback } from 'react'

export default function Sidebar() {
  const [indexing, setIndexing] = useState(false)
  const [indexMsg, setIndexMsg] = useState(null)
  const [syncing, setSyncing] = useState(false)
  const [syncMsg, setSyncMsg] = useState(null)
  const [stats, setStats] = useState(null)
  const [statsLoading, setStatsLoading] = useState(false)
  const [statsError, setStatsError] = useState(null)

  const fetchStats = useCallback(async () => {
    setStatsLoading(true)
    setStatsError(null)
    try {
      const res = await fetch('/index/stats')
      if (!res.ok) throw new Error(`${res.status} ${res.statusText}`)
      setStats(await res.json())
    } catch (e) {
      setStatsError(e.message)
    } finally {
      setStatsLoading(false)
    }
  }, [])

  useEffect(() => { fetchStats() }, [fetchStats])

  const handleIndex = async () => {
    setIndexing(true)
    setIndexMsg(null)
    try {
      const res = await fetch('/index/codebase', { method: 'POST' })
      if (!res.ok) throw new Error(`${res.status} ${res.statusText}`)
      const data = await res.json()
      setIndexMsg(data.message || 'Indexing complete')
      fetchStats()
    } catch (e) {
      setIndexMsg(`Error: ${e.message}`)
    } finally {
      setIndexing(false)
    }
  }

  const handleSync = async () => {
    setSyncing(true)
    setSyncMsg(null)
    try {
      const res = await fetch('/lineage/sync', { method: 'POST' })
      if (!res.ok) throw new Error(`${res.status} ${res.statusText}`)
      const data = await res.json()
      setSyncMsg(`Synced ${data.events_synced ?? '?'} events`)
      fetchStats()
    } catch (e) {
      setSyncMsg(`Error: ${e.message}`)
    } finally {
      setSyncing(false)
    }
  }

  const statItems = stats
    ? [
        { label: 'Code Chunks', value: stats.code_chunks },
        { label: 'Log Entries', value: stats.log_entries },
        { label: 'DAG Metadata', value: stats.dag_metadata },
        { label: 'Lineage Events', value: stats.lineage_events },
      ]
    : []

  return (
    <aside className="flex w-64 shrink-0 flex-col gap-4 border-r border-gray-700 bg-gray-950 p-4">
      <h2 className="text-xs font-semibold tracking-wider text-gray-500 uppercase">Actions</h2>

      <button
        onClick={handleIndex}
        disabled={indexing}
        className="rounded bg-blue-600 px-3 py-2 text-sm font-medium text-white hover:bg-blue-700 disabled:opacity-50"
      >
        {indexing ? 'Indexing...' : 'Index Codebase'}
      </button>
      {indexMsg && (
        <p className={`text-xs ${indexMsg.startsWith('Error') ? 'text-red-400' : 'text-green-400'}`}>{indexMsg}</p>
      )}

      <button
        onClick={handleSync}
        disabled={syncing}
        className="rounded bg-purple-600 px-3 py-2 text-sm font-medium text-white hover:bg-purple-700 disabled:opacity-50"
      >
        {syncing ? 'Syncing...' : 'Sync Lineage to VectorDB'}
      </button>
      {syncMsg && (
        <p className={`text-xs ${syncMsg.startsWith('Error') ? 'text-red-400' : 'text-green-400'}`}>{syncMsg}</p>
      )}

      <div className="mt-4 border-t border-gray-700 pt-4">
        <div className="mb-2 flex items-center justify-between">
          <h2 className="text-xs font-semibold tracking-wider text-gray-500 uppercase">ChromaDB Stats</h2>
          <button
            onClick={fetchStats}
            disabled={statsLoading}
            className="text-xs text-gray-400 hover:text-white disabled:opacity-50"
          >
            {statsLoading ? '...' : 'Refresh'}
          </button>
        </div>
        {statsError && <p className="text-xs text-red-400">{statsError}</p>}
        {stats && (
          <div className="grid grid-cols-2 gap-2">
            {statItems.map((s) => (
              <div key={s.label} className="rounded bg-gray-800 p-2 text-center">
                <p className="text-lg font-bold text-white">{s.value ?? '—'}</p>
                <p className="text-[10px] text-gray-400">{s.label}</p>
              </div>
            ))}
          </div>
        )}
      </div>
    </aside>
  )
}
