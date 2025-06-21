import {useEffect, useState} from "react"
import "../styles/schedulerStatus.css"

/* типы */
type JobStatus = "pending" | "started" | "done" | "success" | "error"

interface ParseRun {
    id: number
    time: string  // 21:37 или 2025-06-10 21:37
    status: JobStatus
    detail: string | null
}

interface SchedulerOverview {
    status: "running" | "stopped"
    intervals: string[]  // 12:10, 15:15
    runs: ParseRun[]
}

/* утилиты */
const statusLabel: Record<JobStatus, string> = {
    pending: "В очереди",
    started: "В процессе",
    success: "Успех",
    done: "Готово",
    error: "Ошибка"
}
const statusDotClass: Record<JobStatus, string> = {
    pending: "status-dot status-wait",
    started: "status-dot status-wait",
    success: "status-dot status-ok",
    done: "status-dot status-ok",
    error: "status-dot status-err"
}

/* компонент */
export default function SchedulerStatusPanel() {
    const [data, setData] = useState<SchedulerOverview | null>(null)

    /* polling каждые 5 секунд */
    useEffect(() => {
        const fetchData = () =>
            fetch("/api/scheduler/overview")
                .then(r => r.json())
                .then(setData)
                .catch(console.error)

        fetchData()
        const id = setInterval(fetchData, 5_000)
        return () => clearInterval(id)
    }, [])

    if (!data) {
        return <div className="schedule-wrapper">Загрузка...</div>
    }

    return (
        <div className="schedule-wrapper">
            <table>
                <thead>
                <tr>
                    <th>Время</th>
                    <th>Статус</th>
                    <th>Детали</th>
                </tr>
                </thead>

                <tbody>
                {data.runs.map(run => (
                    <tr key={run.id}>
                        <td>{run.time}</td>
                        <td>
                            <span className={statusDotClass[run.status]}/>
                            {statusLabel[run.status]}
                        </td>
                        <td>{run.detail ?? "—"}</td>
                    </tr>
                ))}
                </tbody>
            </table>
        </div>
    )
}
