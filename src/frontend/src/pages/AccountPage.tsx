import {useEffect, useState} from "react"
import Navigation from "../components/Navigation"
import MobileNavbar from "../components/MobileNavbar"
import {
    getAccount,
    postAccount,
    getBotSettings,
    postBotSettings,
    getBotConfig,
    patchBotConfig
} from "../api"
import "../styles/setup.css"
import "../styles/home.css"

export default function AccountPage() {
    const [login, setLogin] = useState("")
    const [password, setPassword] = useState("")
    const [userEmail, setUserEmail] = useState("")
    const [scheduleTimes, setScheduleTimes] = useState("")
    const [calendarName, setCalendarName] = useState("")
    const [file, setFile] = useState<File | null>(null)
    const [dragActive, setDragActive] = useState(false)
    const [errors, setErrors] = useState<{ time?: string; file?: string }>({})

    const [botEnabled, setBotEnabled] = useState(false)
    const [botLoading, setBotLoading] = useState(true)
    const [botStatusTxt, setBotStatusTxt] = useState("Загрузка...")
    const [botToken, setBotToken] = useState("")
    const [adminIds, setAdminIds] = useState("")

    useEffect(() => {
        getAccount().then((data) => {
            setLogin(data.USERNAME || "")
            setPassword(data.PASSWORD || "")
            setUserEmail(data.USER_MAIL_ACCOUNT || "")
            setScheduleTimes(data.PARSING_INTERVALS || "")
            setCalendarName(data.CALENDAR_NAME || "")
        })

        getBotSettings()
            .then((s) => {
                setBotEnabled(!!s.bot_enabled)
                setBotStatusTxt(s.bot_enabled ? "Работает" : "Остановлен")
            })
            .catch(() => setBotStatusTxt("Ошибка"))

        getBotConfig()
            .then((c) => {
                setBotToken(c.bot_token ?? "")
                setAdminIds(c.admin_ids ?? "")
            })
            .finally(() => setBotLoading(false))
    }, [])

    const toggleBot = () => {
        setBotLoading(true)
        postBotSettings(!botEnabled)
            .then(() => {
                setBotEnabled((prev) => !prev)
                setBotStatusTxt(!botEnabled ? "Работает" : "Остановлен")
            })
            .catch(() => alert("Не удалось изменить состояние бота"))
            .finally(() => setBotLoading(false))
    }

    const saveBotConfig = () => {
        patchBotConfig({bot_token: botToken, admin_ids: adminIds})
            .then(() => alert("Конфигурация бота сохранена"))
            .catch(() => alert("Ошибка при сохранении конфигурации бота"))
    }

    const validateTimeFormat = (input: string) => {
        const times = input.split(",").map((t) => t.trim())
        const timeRegex = /^\d{1,2}:\d{2}$/
        return times.every((t) => timeRegex.test(t))
    }

    const handleSubmit = async (e: React.FormEvent) => {
        e.preventDefault()
        const newErrors: typeof errors = {}

        if (!scheduleTimes.trim()) {
            newErrors.time = "Это поле обязательно"
        } else if (!validateTimeFormat(scheduleTimes)) {
            newErrors.time = "Неверный формат. Пример: 08:00,13:30,18:00"
        }

        if (Object.keys(newErrors).length > 0) {
            setErrors(newErrors)
            return
        }

        const form = new FormData()
        form.append("username", login)
        form.append("password", password)
        form.append("user_mail_account", userEmail)
        form.append("parsing_intervals", scheduleTimes)
        form.append("calendar_name", calendarName)
        if (file) form.append("file", file)

        const res = await postAccount(form)
        if (res.ok) {
            alert("Данные успешно обновлены")
            setErrors({})
            setFile(null)
        }
    }

    return (
        <>
            <Navigation/>
            <MobileNavbar active="account"/>
            <div className="content-wrapper">
                <div className="project">

                    <h2>Telegram-бот</h2>
                    <div className="sub-card bot-card">
                        <div className="bot-row">
                            <label className="switch">
                                <input
                                    type="checkbox"
                                    checked={botEnabled}
                                    disabled={botLoading}
                                    onChange={toggleBot}
                                />
                                <span className="slider round"/>
                            </label>
                            <span className="bot-status">
                Статус:&nbsp;
                                <span className={botEnabled ? "ok" : "offline"}>{botStatusTxt}</span>
              </span>
                        </div>

                        <div className="bot-fields">
                            <label>
                                BOT Token
                                <input
                                    type="password"
                                    value={botToken}
                                    onChange={(e) => setBotToken(e.target.value)}
                                />
                            </label>
                            <label>
                                Admin ID
                                <input
                                    type="text"
                                    value={adminIds}
                                    onChange={(e) => setAdminIds(e.target.value)}
                                />
                            </label>
                            <button type="button" className="bot-save" onClick={saveBotConfig}>
                                Сохранить конфиг бота
                            </button>
                        </div>
                    </div>

                    <h2 style={{marginTop: "2rem"}}>Редактирование данных</h2>
                    <p className="description">
                        Вы можете обновить данные, указанные ранее, или заменить credentials.json
                    </p>

                    <form
                        onSubmit={handleSubmit}
                        className="project-features"
                        onDragOver={(e) => {
                            e.preventDefault()
                            setDragActive(true)
                        }}
                        onDragLeave={() => setDragActive(false)}
                        onDrop={(e) => {
                            e.preventDefault()
                            setDragActive(false)
                            const f = e.dataTransfer.files?.[0]
                            if (f) setFile(f)
                        }}
                    >
                        <label>
                            Логин ~ ВВГУ
                            <input
                                type="text"
                                value={login}
                                onChange={(e) => setLogin(e.target.value)}
                                required
                            />
                        </label>

                        <label>
                            Пароль ~ ВВГУ
                            <input
                                type="password"
                                value={password}
                                onChange={(e) => setPassword(e.target.value)}
                                required
                            />
                        </label>

                        <label>
                            Email Google аккаунта
                            <input
                                type="email"
                                value={userEmail}
                                onChange={(e) => setUserEmail(e.target.value)}
                                required
                            />
                        </label>

                        <label>
                            Время синхронизации
                            <input
                                type="text"
                                value={scheduleTimes}
                                onChange={(e) => setScheduleTimes(e.target.value)}
                                placeholder="например: 08:00,13:30,18:00"
                            />
                            {errors.time && <div className="form-error">{errors.time}</div>}
                        </label>

                        <label>
                            Название календаря
                            <input
                                type="text"
                                value={calendarName}
                                onChange={(e) => setCalendarName(e.target.value)}
                                placeholder="Например: ВВГУ_Расписание"
                            />
                        </label>

                        <div
                            className={`file-drop-zone ${dragActive ? "drag-active" : ""}`}
                            onClick={() => document.getElementById("fileInput")?.click()}
                        >
                            {file ? `Файл: ${file.name}` : "Перетащите сюда новый credentials.json или кликните для выбора (опционально)"}
                            <input
                                type="file"
                                id="fileInput"
                                accept=".json"
                                style={{display: "none"}}
                                onChange={(e) => setFile(e.target.files?.[0] || null)}
                            />
                        </div>
                        {errors.file && <div className="form-error">{errors.file}</div>}

                        <button type="submit">Сохранить изменения</button>
                    </form>
                </div>
            </div>
        </>
    )
}
