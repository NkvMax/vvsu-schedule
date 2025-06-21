import { useEffect, useState } from "react"
import "../styles/timeline.css"

type Day = { date: string; status: "ok" | "warn" | "error"; message?: string }

export default function StatusTimelinePanel() {
  const [expanded, setExpanded] = useState(
    localStorage.getItem("timelineExpanded") === "true"
  )
  const [days, setDays] = useState<Day[]>([])

  useEffect(() => {
    fetch("/api/scheduler/timeline?days=30")
      .then(r => r.json())
      .then(setDays)
      .catch(console.error)
  }, [])

  const today = new Date().toISOString().slice(0, 10)
  const toggle = () => {
    const next = !expanded
    setExpanded(next)
    localStorage.setItem("timelineExpanded", String(next))
  }

  return (
    <div className={`logs-wrapper timeline ${expanded ? "full-width" : ""}`}>
      <div className={`logs-panel timeline ${expanded ? "expanded" : ""}`}>
        <div className="timeline-header">
          <h3>schedule-vvsu</h3>
          <button className="toggle-btn" onClick={toggle}>
            {expanded ? "➖ Скрыть" : "➕ Развернуть"}
          </button>
        </div>

        {expanded && (
          <div className="timeline-body">
            {days.length === 0 ? (
              <p className="empty">Нет данных</p>
            ) : (
              <div className="timeline-bar">
                {days.map((d, i) => (
                  <div
                    key={i}
                    className={`day day-${d.status}${
                      d.date === today ? " today" : ""
                    }`}
                    title={`${d.date}\n${d.status}`}
                  />
                ))}
              </div>
            )}
          </div>
        )}
      </div>
    </div>
  )
}

