import {useEffect, useRef, useState} from "react"
import "../styles/logs.css"

interface LogEntry {
    id: number
    ts: string
    level: string
    msg: string
}

const tz = "Asia/Vladivostok"

function fmt(iso: string) {
    return new Date(iso + "Z").toLocaleString("ru-RU", {timeZone: tz})
}

function clean(m: string) {
    const re = /^\d{4}-\d{2}-\d{2} \d{2}:\d{2}:\d{2},\d{3} (INFO|ERROR|WARNING|DEBUG):\s?/;
    const m1 = m.match(re)
    if (m1) return m.slice(m1[0].length)
    return m.replace(/^\d{4}-\d{2}-\d{2} \d{2}:\d{2}:\d{2},\d{3}\s?/, "")
}

export default function LogsPanel() {
    const [logs, setLogs] = useState<LogEntry[]>([])
    const [lastId, setLastId] = useState(0)
    const [expanded, setExpanded] = useState(() => localStorage.getItem("logsExpanded") === "true")
    const [autoScroll, setAutoScroll] = useState(() => localStorage.getItem("logsAutoScroll") !== "false")
    const [hasScrolled, setHasScrolled] = useState(false)
    const tail = useRef<HTMLDivElement>(null)

    useEffect(() => {
        const fetchLogs = () => {
            fetch("/api/logs/sql?after_id=" + lastId)
                .then(r => r.json())
                .then((chunk: LogEntry[]) => {
                    if (chunk.length) {
                        setLogs(prev => {
                            const updated = [...prev, ...chunk].slice(-100)
                            setLastId(updated[updated.length - 1].id)
                            return updated
                        })
                    }
                })
                .catch(console.error)
        }

        fetchLogs()
        const id = setInterval(fetchLogs, 5000)
        return () => clearInterval(id)
    }, [lastId])

    useEffect(() => {
        if (autoScroll && !hasScrolled && tail.current && logs.length) {
            tail.current.scrollIntoView({behavior: "smooth"})
            setHasScrolled(true)
        }
    }, [logs, autoScroll, hasScrolled])

    useEffect(() => {
        if (expanded && autoScroll && tail.current) {
            tail.current.scrollIntoView({behavior: "smooth"})
        }
    }, [expanded, autoScroll])

    const toggle = () => {
        const nxt = !expanded
        setExpanded(nxt)
        localStorage.setItem("logsExpanded", String(nxt))
        if (nxt) setHasScrolled(false)
    }

    const follow = (v: boolean) => {
        setAutoScroll(v)
        localStorage.setItem("logsAutoScroll", String(v))
    }

    return (
        <div className={`logs-wrapper ${expanded ? "full-width" : ""}`}>
            <div className={`logs-panel ${expanded ? "expanded" : ""}`}>
                <div className="logs-header">
                    <h3>Логи (в реальном времени)</h3>
                    <div style={{display: "flex", alignItems: "center", gap: "1em"}}>
                        {expanded && (
                            <label style={{fontSize: ".9em"}}>
                                <input type="checkbox" checked={autoScroll}
                                       onChange={e => follow(e.target.checked)}/> Следить
                            </label>
                        )}
                        <button className="toggle-btn" onClick={toggle}>{expanded ? "➖ Скрыть" : "➕ Раскрыть"}</button>
                    </div>
                </div>

                {expanded && (
                    <div className="logs-body">
                        {logs.length ? (
                            <>
                                {logs.map(l => (
                                    <pre key={l.id} className={`log-line log-${l.level.toLowerCase()}`}>
                    <span className="log-datetime">[{fmt(l.ts)}]</span>{" "}
                                        <span
                                            className={`log-level log-${l.level.toLowerCase()}`}>[{l.level}]</span>{" "}
                                        {clean(l.msg)}
                  </pre>
                                ))}
                                <div ref={tail}/>
                            </>
                        ) : (
                            <p className="empty">Логи отсутствуют</p>
                        )}
                    </div>
                )}
            </div>
        </div>
    )
}
