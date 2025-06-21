import {useEffect, useState} from "react"
import Navigation from "../components/Navigation"
import MobileNavbar from "../components/MobileNavbar"
import {getHealth, postScheduler, postSync} from "../api"
import TabbedPanel from "../components/TabbedPanel"

import syncIcon from "../assets/icons/sync.png"
import playIcon from "../assets/icons/play.png"
import stopIcon from "../assets/icons/pause.png"

import "../styles/home.css"
import "../styles/logs.css"
import "../styles/schedulerStatus.css"
import "../styles/tabs.css"

export default function HomePage() {
    const [server, setServer] = useState<"ok" | "offline">("offline")
    const [scheduler, setScheduler] = useState<"running" | "stopped">("stopped")

    /* проверяем сервер и статус планировщика */
    useEffect(() => {
        getHealth().then(r => setServer(r.status === "ok" ? "ok" : "offline"))
        fetch("/api/scheduler/status")
            .then(r => r.json())
            .then(r => setScheduler(r.status))
            .catch(() => setScheduler("stopped"))
    }, [])

    /* обработчики кликов */
    const handleSync = () =>
        postSync().then(r => alert(r.details)).catch(console.error)

    const toggleScheduler = () => {
        const action = scheduler === "running" ? "stop" : "start"
        postScheduler(action)
            .then(r => {
                alert(r.scheduler)
                setScheduler(prev => (prev === "running" ? "stopped" : "running"))
            })
            .catch(console.error)
    }

    /* JSX */
    return (
        <>
            <Navigation/>
            <MobileNavbar active="home"/>

            <main className="home-wrapper">
                <section className="card">
                    <p className="server-status">
                        Подключено к серверу :
                        <span className={server === "ok" ? "ok" : "offline"}> {server}</span>
                    </p>

                    {/* плитка "синхронизация" */}
                    <div className="sub-card">
                        <h4>Синхронизация</h4>
                        <button className="action-btn" onClick={handleSync}>
                            <img src={syncIcon} alt="" className="icon"/>
                            Синхронизировать сейчас
                        </button>
                    </div>

                    {/* плитка "планировщик" */}
                    <div className="sub-card">
                        <h4>Планировщик</h4>
                        <button
                            className={`action-btn ${scheduler === "running" ? "stop" : ""}`}
                            onClick={toggleScheduler}
                        >
                            <img
                                src={scheduler === "running" ? stopIcon : playIcon}
                                alt=""
                                className="icon"
                            />
                            {scheduler === "running" ? "Остановить" : "Запустить"}
                        </button>
                    </div>
                </section>

                <TabbedPanel/>
            </main>
        </>
    )
}
