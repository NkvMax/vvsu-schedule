import { useState } from "react"
import LogsPanel from "./LogsPanel"
import SchedulerStatusPanel from "./SchedulerStatusPanel"
import "../styles/tabs.css"

export default function TabbedPanel() {
  const [tab, setTab] = useState<"logs" | "schedule">("logs")

  return (
    <section className="tab-wrapper">
      <div className="tab-bar">
        <button
          className={`tab-btn ${tab === "logs" ? "active" : ""}`}
          onClick={() => setTab("logs")}
        >
          Логи
        </button>
        <button
          className={`tab-btn ${tab === "schedule" ? "active" : ""}`}
          onClick={() => setTab("schedule")}
        >
          Расписание
        </button>
      </div>

      <div className="tab-body">
        {tab === "logs" ? <LogsPanel /> : <SchedulerStatusPanel />}
      </div>
    </section>
  )
}
