import { Routes, Route } from 'react-router-dom'
import Navbar from './components/Navbar'
import Sidebar from './components/Sidebar'
import ChatPage from './pages/ChatPage'
import LogAnalysisPage from './pages/LogAnalysisPage'
import AirflowPage from './pages/AirflowPage'
import K8sPage from './pages/K8sPage'
import LineagePage from './pages/LineagePage'

export default function App() {
  return (
    <div className="flex h-screen flex-col">
      <Navbar />
      <div className="flex flex-1 overflow-hidden">
        <Sidebar />
        <main className="flex-1 overflow-y-auto p-6">
          <Routes>
            <Route path="/" element={<ChatPage />} />
            <Route path="/logs" element={<LogAnalysisPage />} />
            <Route path="/airflow" element={<AirflowPage />} />
            <Route path="/k8s" element={<K8sPage />} />
            <Route path="/lineage" element={<LineagePage />} />
          </Routes>
        </main>
      </div>
    </div>
  )
}
