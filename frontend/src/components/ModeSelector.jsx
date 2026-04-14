export default function ModeSelector({ value, onChange }) {
  return (
    <select
      value={value}
      onChange={(e) => onChange(e.target.value)}
      className="rounded border border-gray-600 bg-gray-800 px-3 py-2 text-sm text-gray-200 focus:border-blue-500 focus:outline-none"
    >
      <option value="auto">auto</option>
      <option value="heuristic">heuristic</option>
      <option value="llm">llm</option>
    </select>
  )
}
