import { NavLink } from 'react-router-dom'

const links = [
  { to: '/', label: 'Chat' },
  { to: '/logs', label: 'Logs' },
  { to: '/airflow', label: 'Airflow' },
  { to: '/k8s', label: 'K8s' },
  { to: '/lineage', label: 'Lineage' },
]

export default function Navbar() {
  return (
    <nav className="flex items-center gap-6 border-b border-gray-700 bg-gray-950 px-6 py-3">
      <span className="mr-4 text-lg font-bold text-white">BigData Prototype</span>
      {links.map((l) => (
        <NavLink
          key={l.to}
          to={l.to}
          end={l.to === '/'}
          className={({ isActive }) =>
            `text-sm font-medium transition-colors ${isActive ? 'text-blue-400' : 'text-gray-400 hover:text-gray-200'}`
          }
        >
          {l.label}
        </NavLink>
      ))}
    </nav>
  )
}
