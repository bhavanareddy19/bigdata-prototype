import { useState, useEffect } from 'react'

export default function LineagePage() {
  const [namespaces, setNamespaces] = useState([])
  const [nsLoading, setNsLoading] = useState(true)
  const [nsError, setNsError] = useState(null)
  const [selected, setSelected] = useState('')
  const [jobs, setJobs] = useState([])
  const [datasets, setDatasets] = useState([])
  const [detailLoading, setDetailLoading] = useState(false)
  const [detailError, setDetailError] = useState(null)

  useEffect(() => {
    const load = async () => {
      try {
        const res = await fetch('/lineage/namespaces')
        if (!res.ok) throw new Error(`${res.status} ${res.statusText}`)
        const data = await res.json()
        setNamespaces(Array.isArray(data) ? data : data.namespaces || [])
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

  return (
    <div>
      <h1 className="mb-4 text-xl font-bold text-white">Lineage</h1>

      {nsLoading && <p className="text-sm text-gray-400">Loading namespaces...</p>}
      {nsError && <p className="text-sm text-red-400">{nsError}</p>}

      {!nsLoading && !nsError && (
        <select
          value={selected}
          onChange={(e) => setSelected(e.target.value)}
          className="rounded border border-gray-600 bg-gray-800 px-3 py-2 text-sm text-gray-200 focus:border-blue-500 focus:outline-none"
        >
          <option value="">Select namespace...</option>
          {namespaces.map((ns) => (
            <option key={typeof ns === 'string' ? ns : ns.name} value={typeof ns === 'string' ? ns : ns.name}>
              {typeof ns === 'string' ? ns : ns.name}
            </option>
          ))}
        </select>
      )}

      {detailLoading && <p className="mt-4 text-sm text-gray-400">Loading...</p>}
      {detailError && <p className="mt-4 text-sm text-red-400">{detailError}</p>}

      {selected && !detailLoading && !detailError && (
        <div className="mt-6 grid grid-cols-2 gap-6">
          <div>
            <h2 className="mb-2 text-sm font-semibold text-gray-400 uppercase">Jobs ({jobs.length})</h2>
            <div className="space-y-2">
              {jobs.length === 0 && <p className="text-sm text-gray-500">No jobs found</p>}
              {jobs.map((j, i) => (
                <div key={i} className="rounded border border-gray-700 bg-gray-800 p-3">
                  <p className="text-sm font-medium text-white">{j.name || j.id || JSON.stringify(j)}</p>
                  {j.namespace && <p className="text-xs text-gray-500">{j.namespace}</p>}
                </div>
              ))}
            </div>
          </div>

          <div>
            <h2 className="mb-2 text-sm font-semibold text-gray-400 uppercase">Datasets ({datasets.length})</h2>
            <div className="space-y-2">
              {datasets.length === 0 && <p className="text-sm text-gray-500">No datasets found</p>}
              {datasets.map((d, i) => (
                <div key={i} className="rounded border border-gray-700 bg-gray-800 p-3">
                  <p className="text-sm font-medium text-white">{d.name || d.id || JSON.stringify(d)}</p>
                  {d.namespace && <p className="text-xs text-gray-500">{d.namespace}</p>}
                </div>
              ))}
            </div>
          </div>
        </div>
      )}
    </div>
  )
}
