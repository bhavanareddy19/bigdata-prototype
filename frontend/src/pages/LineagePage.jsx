import { useState, useEffect } from 'react'

// ── Helpers ───────────────────────────────────────────────────

function getZone(name) {
  if (!name) return 'other'
  if (name.startsWith('landing/')) return 'landing'
  if (name.startsWith('raw/')) return 'raw'
  if (name.startsWith('staging/')) return 'staging'
  if (name.startsWith('processed/')) return 'processed'
  if (name.startsWith('curated/')) return 'curated'
  if (name.startsWith('features/')) return 'features'
  if (name.startsWith('models/')) return 'models'
  if (name.startsWith('external/')) return 'external'
  if (name.startsWith('demo/')) return 'demo'
  return 'other'
}

function getPipelineGroup(jobName) {
  if (!jobName) return 'other'
  if (jobName.startsWith('data_ingestion')) return 'ingestion'
  if (jobName.startsWith('data_transformation')) return 'transformation'
  if (jobName.startsWith('data_quality')) return 'quality'
  if (jobName.startsWith('ml_pipeline')) return 'ml'
  if (jobName.startsWith('demo_pipeline')) return 'demo_pipeline'
  if (jobName.startsWith('demo_observability')) return 'demo_obs'
  return 'other'
}

const ZONE_STYLE = {
  landing:    { dot: 'bg-blue-400',   badge: 'bg-blue-900/60 text-blue-300 border-blue-700' },
  raw:        { dot: 'bg-yellow-400', badge: 'bg-yellow-900/60 text-yellow-300 border-yellow-700' },
  staging:    { dot: 'bg-orange-400', badge: 'bg-orange-900/60 text-orange-300 border-orange-700' },
  processed:  { dot: 'bg-purple-400', badge: 'bg-purple-900/60 text-purple-300 border-purple-700' },
  curated:    { dot: 'bg-green-400',  badge: 'bg-green-900/60 text-green-300 border-green-700' },
  features:   { dot: 'bg-teal-400',   badge: 'bg-teal-900/60 text-teal-300 border-teal-700' },
  models:     { dot: 'bg-pink-400',   badge: 'bg-pink-900/60 text-pink-300 border-pink-700' },
  external:   { dot: 'bg-gray-400',   badge: 'bg-gray-800 text-gray-300 border-gray-600' },
  demo:       { dot: 'bg-cyan-400',   badge: 'bg-cyan-900/60 text-cyan-300 border-cyan-700' },
  other:      { dot: 'bg-gray-500',   badge: 'bg-gray-800 text-gray-400 border-gray-600' },
}

const PIPELINE_META = {
  ingestion:    { label: 'Data Ingestion',    color: 'border-blue-600',   header: 'bg-blue-900/40',   badge: 'bg-blue-700 text-white',   icon: '⬇' },
  transformation:{ label: 'Transformation',   color: 'border-purple-600', header: 'bg-purple-900/40', badge: 'bg-purple-700 text-white', icon: '⚙' },
  quality:      { label: 'Quality Checks',    color: 'border-yellow-600', header: 'bg-yellow-900/40', badge: 'bg-yellow-700 text-white', icon: '✓' },
  ml:           { label: 'ML Pipeline',       color: 'border-green-600',  header: 'bg-green-900/40',  badge: 'bg-green-700 text-white',  icon: '🔬' },
  demo_pipeline:{ label: 'Demo Pipeline',     color: 'border-cyan-600',   header: 'bg-cyan-900/40',   badge: 'bg-cyan-700 text-white',   icon: '▶' },
  demo_obs:     { label: 'Demo Observability',color: 'border-red-600',    header: 'bg-red-900/40',    badge: 'bg-red-700 text-white',    icon: '🔍' },
  other:        { label: 'Other',             color: 'border-gray-600',   header: 'bg-gray-900/40',   badge: 'bg-gray-700 text-white',   icon: '•' },
}

// Pipeline zone overview data
const ZONE_FLOW = [
  { zone: 'external', label: 'External\nAPIs' },
  { zone: 'landing',  label: 'Landing\nZone' },
  { zone: 'raw',      label: 'Raw\nZone' },
  { zone: 'staging',  label: 'Staging\nZone' },
  { zone: 'processed',label: 'Processed\nZone' },
  { zone: 'curated',  label: 'Curated\nZone' },
  { zone: 'features', label: 'Feature\nStore' },
  { zone: 'models',   label: 'Model\nArtifacts' },
]

const ZONE_LABEL_COLORS = {
  external:   'bg-gray-700 border-gray-500 text-gray-300',
  landing:    'bg-blue-900 border-blue-600 text-blue-200',
  raw:        'bg-yellow-900 border-yellow-600 text-yellow-200',
  staging:    'bg-orange-900 border-orange-600 text-orange-200',
  processed:  'bg-purple-900 border-purple-600 text-purple-200',
  curated:    'bg-green-900 border-green-600 text-green-200',
  features:   'bg-teal-900 border-teal-600 text-teal-200',
  models:     'bg-pink-900 border-pink-600 text-pink-200',
}

const PIPELINE_ORDER = ['ingestion', 'transformation', 'quality', 'ml', 'demo_pipeline', 'demo_obs', 'other']

// ── DatasetBadge ─────────────────────────────────────────────

function DatasetBadge({ name }) {
  const zone = getZone(name)
  const style = ZONE_STYLE[zone] || ZONE_STYLE.other
  const short = name.replace(/^[^/]+\//, '') // strip zone prefix
  return (
    <span
      className={`inline-flex items-center gap-1 rounded border px-2 py-0.5 text-xs font-mono ${style.badge}`}
      title={name}
    >
      <span className={`h-1.5 w-1.5 rounded-full ${style.dot} flex-shrink-0`} />
      {short.length > 28 ? short.slice(0, 28) + '…' : short}
    </span>
  )
}

// ── JobCard ──────────────────────────────────────────────────

function JobCard({ job }) {
  const [open, setOpen] = useState(false)
  const inputs = job.inputs || []
  const outputs = job.outputs || []
  const taskName = job.name.includes('.') ? job.name.split('.').slice(1).join('.') : job.name

  return (
    <div className="rounded border border-gray-700 bg-gray-900">
      <button
        onClick={() => setOpen(o => !o)}
        className="flex w-full items-center justify-between px-4 py-3 text-left hover:bg-gray-800/50 transition-colors"
      >
        <div className="flex items-center gap-3">
          <span className="text-gray-500 text-xs">{open ? '▾' : '▸'}</span>
          <span className="text-sm font-medium text-white font-mono">{taskName}</span>
        </div>
        <div className="flex items-center gap-2 text-xs text-gray-500">
          {inputs.length > 0 && <span>{inputs.length} in</span>}
          {outputs.length > 0 && <span>{outputs.length} out</span>}
          {inputs.length === 0 && outputs.length === 0 && <span className="text-gray-600">no datasets</span>}
        </div>
      </button>

      {open && (
        <div className="border-t border-gray-700/60 px-4 py-3">
          <div className="flex flex-col gap-3 sm:flex-row sm:items-start sm:gap-4">
            {/* Inputs */}
            <div className="flex-1">
              <p className="mb-1.5 text-xs font-semibold text-gray-500 uppercase tracking-wide">Reads from</p>
              {inputs.length === 0 ? (
                <span className="text-xs text-gray-600 italic">no inputs</span>
              ) : (
                <div className="flex flex-wrap gap-1.5">
                  {inputs.map((inp, i) => (
                    <DatasetBadge key={i} name={inp.name || inp} />
                  ))}
                </div>
              )}
            </div>

            {/* Arrow */}
            <div className="flex items-center justify-center text-gray-600 text-lg sm:pt-5">→</div>

            {/* Outputs */}
            <div className="flex-1">
              <p className="mb-1.5 text-xs font-semibold text-gray-500 uppercase tracking-wide">Writes to</p>
              {outputs.length === 0 ? (
                <span className="text-xs text-gray-600 italic">no outputs</span>
              ) : (
                <div className="flex flex-wrap gap-1.5">
                  {outputs.map((out, i) => (
                    <DatasetBadge key={i} name={out.name || out} />
                  ))}
                </div>
              )}
            </div>
          </div>
        </div>
      )}
    </div>
  )
}

// ── PipelineSection ──────────────────────────────────────────

function PipelineSection({ group, jobs }) {
  const [open, setOpen] = useState(true)
  const meta = PIPELINE_META[group] || PIPELINE_META.other
  // Only show leaf tasks (those with a dot in the name — task-level, not DAG-level)
  const taskJobs = jobs.filter(j => j.name.includes('.'))

  return (
    <div className={`rounded-lg border ${meta.color} overflow-hidden`}>
      <button
        onClick={() => setOpen(o => !o)}
        className={`flex w-full items-center justify-between px-4 py-3 ${meta.header} hover:brightness-110 transition-all`}
      >
        <div className="flex items-center gap-3">
          <span className="text-lg">{meta.icon}</span>
          <span className="font-semibold text-white">{meta.label}</span>
          <span className={`rounded-full px-2 py-0.5 text-xs ${meta.badge}`}>
            {taskJobs.length} tasks
          </span>
        </div>
        <span className="text-gray-400 text-sm">{open ? '▾' : '▸'}</span>
      </button>

      {open && (
        <div className="space-y-2 p-3">
          {taskJobs.length === 0 ? (
            <p className="text-sm text-gray-500 px-2 py-1 italic">No tasks with lineage data yet</p>
          ) : (
            taskJobs.map((j, i) => <JobCard key={i} job={j} />)
          )}
        </div>
      )}
    </div>
  )
}

// ── ZoneFlow (top overview) ──────────────────────────────────

function ZoneFlow({ datasets }) {
  const occupiedZones = new Set(datasets.map(d => getZone(d.name || d)))

  return (
    <div className="rounded-lg border border-gray-700 bg-gray-900/60 p-4">
      <p className="mb-3 text-xs font-semibold uppercase tracking-wider text-gray-500">Data Flow Overview</p>
      <div className="flex flex-wrap items-center gap-0">
        {ZONE_FLOW.map(({ zone, label }, i) => {
          const active = occupiedZones.has(zone)
          const colorClass = ZONE_LABEL_COLORS[zone] || 'bg-gray-700 border-gray-500 text-gray-400'
          return (
            <div key={zone} className="flex items-center">
              <div className={`rounded border px-3 py-2 text-center text-xs font-medium whitespace-pre-line transition-all
                ${active ? colorClass : 'bg-gray-800/30 border-gray-700 text-gray-600'}`}
              >
                {label}
                {active && (
                  <div className="mt-1 text-[10px] opacity-70">
                    {datasets.filter(d => getZone(d.name || d) === zone).length} datasets
                  </div>
                )}
              </div>
              {i < ZONE_FLOW.length - 1 && (
                <div className={`px-1 text-lg font-bold ${active ? 'text-gray-400' : 'text-gray-700'}`}>→</div>
              )}
            </div>
          )
        })}
      </div>
    </div>
  )
}

// ── Main Page ────────────────────────────────────────────────

export default function LineagePage() {
  const [namespaces, setNamespaces] = useState([])
  const [nsLoading, setNsLoading] = useState(true)
  const [nsError, setNsError] = useState(null)
  const [selected, setSelected] = useState('')
  const [jobs, setJobs] = useState([])
  const [datasets, setDatasets] = useState([])
  const [detailLoading, setDetailLoading] = useState(false)
  const [detailError, setDetailError] = useState(null)
  const [syncing, setSyncing] = useState(false)
  const [syncMsg, setSyncMsg] = useState(null)

  useEffect(() => {
    const load = async () => {
      try {
        const res = await fetch('/lineage/namespaces')
        if (!res.ok) throw new Error(`${res.status} ${res.statusText}`)
        const data = await res.json()
        const nsList = Array.isArray(data) ? data : data.namespaces || []
        setNamespaces(nsList)
        // Auto-select first namespace
        if (nsList.length > 0) {
          const first = typeof nsList[0] === 'string' ? nsList[0] : nsList[0].name
          setSelected(first)
        }
      } catch (e) {
        setNsError(e.message)
      } finally {
        setNsLoading(false)
      }
    }
    load()
  }, [])

  useEffect(() => {
    if (!selected) return
    const load = async () => {
      setDetailLoading(true)
      setDetailError(null)
      try {
        const [jobsRes, dsRes] = await Promise.all([
          fetch(`/lineage/jobs/${encodeURIComponent(selected)}`),
          fetch(`/lineage/datasets/${encodeURIComponent(selected)}`),
        ])
        if (!jobsRes.ok) throw new Error(`Jobs: ${jobsRes.status}`)
        if (!dsRes.ok) throw new Error(`Datasets: ${dsRes.status}`)
        const jobsData = await jobsRes.json()
        const dsData = await dsRes.json()
        setJobs(Array.isArray(jobsData) ? jobsData : jobsData.jobs || [])
        setDatasets(Array.isArray(dsData) ? dsData : dsData.datasets || [])
      } catch (e) {
        setDetailError(e.message)
      } finally {
        setDetailLoading(false)
      }
    }
    load()
  }, [selected])

  const handleSync = async () => {
    setSyncing(true)
    setSyncMsg(null)
    try {
      const res = await fetch(`/lineage/sync?namespace=${encodeURIComponent(selected || 'bigdata-platform')}`, { method: 'POST' })
      const data = await res.json()
      setSyncMsg(`Synced ${data.synced_events} events to VectorDB`)
    } catch (e) {
      setSyncMsg('Sync failed: ' + e.message)
    } finally {
      setSyncing(false)
    }
  }

  // Group jobs by pipeline
  const grouped = {}
  for (const j of jobs) {
    const g = getPipelineGroup(j.name || '')
    if (!grouped[g]) grouped[g] = []
    grouped[g].push(j)
  }

  const nsName = typeof (namespaces[0]) === 'string' ? namespaces[0] : namespaces[0]?.name

  return (
    <div className="space-y-5">
      {/* Header */}
      <div className="flex items-center justify-between">
        <div>
          <h1 className="text-xl font-bold text-white">Data Lineage</h1>
          <p className="text-xs text-gray-500 mt-0.5">Track data flow from source to model — powered by OpenLineage + Marquez</p>
        </div>
        <div className="flex items-center gap-3">
          {!nsLoading && !nsError && namespaces.length > 1 && (
            <select
              value={selected}
              onChange={(e) => setSelected(e.target.value)}
              className="rounded border border-gray-600 bg-gray-800 px-3 py-1.5 text-sm text-gray-200"
            >
              {namespaces.map((ns) => {
                const val = typeof ns === 'string' ? ns : ns.name
                return <option key={val} value={val}>{val}</option>
              })}
            </select>
          )}
          {selected && (
            <button
              onClick={handleSync}
              disabled={syncing}
              className="rounded bg-indigo-600 hover:bg-indigo-500 disabled:opacity-50 px-3 py-1.5 text-sm text-white transition-colors"
            >
              {syncing ? 'Syncing…' : 'Sync to VectorDB'}
            </button>
          )}
        </div>
      </div>

      {syncMsg && (
        <p className="text-sm text-indigo-300 bg-indigo-900/30 border border-indigo-700 rounded px-3 py-2">{syncMsg}</p>
      )}

      {nsLoading && <p className="text-sm text-gray-400">Loading namespaces…</p>}
      {nsError && <p className="text-sm text-red-400">Error: {nsError}</p>}
      {detailError && <p className="text-sm text-red-400">Error: {detailError}</p>}
      {detailLoading && <p className="text-sm text-gray-400">Loading lineage data…</p>}

      {selected && !detailLoading && !detailError && (
        <>
          {/* Zone Flow Overview */}
          <ZoneFlow datasets={datasets} />

          {/* Stats Row */}
          <div className="grid grid-cols-3 gap-3">
            <div className="rounded border border-gray-700 bg-gray-800 p-3 text-center">
              <p className="text-2xl font-bold text-white">{jobs.filter(j => j.name.includes('.')).length}</p>
              <p className="text-xs text-gray-400 mt-0.5">Tasks Tracked</p>
            </div>
            <div className="rounded border border-gray-700 bg-gray-800 p-3 text-center">
              <p className="text-2xl font-bold text-white">{datasets.length}</p>
              <p className="text-xs text-gray-400 mt-0.5">Datasets</p>
            </div>
            <div className="rounded border border-gray-700 bg-gray-800 p-3 text-center">
              <p className="text-2xl font-bold text-white">{Object.keys(grouped).length}</p>
              <p className="text-xs text-gray-400 mt-0.5">Pipelines</p>
            </div>
          </div>

          {/* Pipeline Sections */}
          <div className="space-y-3">
            <p className="text-xs font-semibold uppercase tracking-wider text-gray-500">Pipeline Task Lineage</p>
            {PIPELINE_ORDER.map(group => {
              if (!grouped[group]) return null
              return <PipelineSection key={group} group={group} jobs={grouped[group]} />
            })}
          </div>

          {/* Dataset Legend */}
          <div className="rounded-lg border border-gray-700 bg-gray-900/60 p-4">
            <p className="mb-3 text-xs font-semibold uppercase tracking-wider text-gray-500">Dataset Zone Legend</p>
            <div className="flex flex-wrap gap-2">
              {Object.entries(ZONE_STYLE).filter(([z]) => z !== 'other').map(([zone, style]) => (
                <span key={zone} className={`inline-flex items-center gap-1.5 rounded border px-2.5 py-1 text-xs ${style.badge}`}>
                  <span className={`h-2 w-2 rounded-full ${style.dot}`} />
                  {zone}/
                </span>
              ))}
            </div>
          </div>
        </>
      )}
    </div>
  )
}
