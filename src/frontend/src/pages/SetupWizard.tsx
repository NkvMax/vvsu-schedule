import {useState} from "react"
import {useNavigate} from "react-router-dom"
import "../styles/projects.css"
import "../styles/setup.css"

export default function SetupWizardPage() {
    const [login, setLogin] = useState("")
    const [password, setPassword] = useState("")
    const [userEmail, setUserEmail] = useState("")
    const [scheduleTimes, setScheduleTimes] = useState("")
    const [calendarName, setCalendarName] = useState("")
    const [file, setFile] = useState<File | null>(null)
    const [dragActive, setDragActive] = useState(false)
    const [errors, setErrors] = useState<{ time?: string; file?: string }>({})
    const navigate = useNavigate()

    const validateTimeFormat = (input: string) => {
        const times = input.split(",").map(t => t.trim())
        const timeRegex = /^\d{1,2}:\d{2}$/ // допустим 8:00 или 13:45
        return times.every(t => timeRegex.test(t))
    }

    const handleSubmit = async (e: React.FormEvent) => {
        e.preventDefault()
        const newErrors: typeof errors = {}

        if (!scheduleTimes.trim()) {
            newErrors.time = "Это поле обязательно"
        } else if (!validateTimeFormat(scheduleTimes)) {
            newErrors.time = "Неверный формат. Пример: 08:00,13:30,18:00"
        }

        if (!file) {
            newErrors.file = "Прикрепите credentials.json"
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
        if (file) {
            form.append("file", file);
        }

        const res = await fetch(import.meta.env.VITE_API_URL + "/setup", {
            method: "POST",
            body: form,
        })
        const json = await res.json()
        if (json.ok) navigate("/home")
    }

    return (
        <div className="content-wrapper">
            <div className="project">
                <h2>Первичная настройка</h2>
                <p className="description">Заполните данные для подключения к ЛК ВВГУ и Google Calendar</p>

                <form onSubmit={handleSubmit} className="project-features"
                      onDragOver={e => {
                          e.preventDefault();
                          setDragActive(true)
                      }}
                      onDragLeave={() => setDragActive(false)}
                      onDrop={e => {
                          e.preventDefault()
                          setDragActive(false)
                          const f = e.dataTransfer.files?.[0]
                          if (f) setFile(f)
                      }}>

                    <label>
                        Логин ~ лк ВВГУ
                        <input type="text" value={login} onChange={e => setLogin(e.target.value)} required/>
                    </label>

                    <label>
                        Пароль ~ лк ВВГУ
                        <input type="password" value={password} onChange={e => setPassword(e.target.value)} required/>
                    </label>

                    <label>
                        Email Google аккаунта
                        <input type="email" value={userEmail} onChange={e => setUserEmail(e.target.value)} required/>
                    </label>

                    <label>
                        Время синхронизации
                        <input
                            type="text"
                            value={scheduleTimes}
                            onChange={e => setScheduleTimes(e.target.value)}
                            placeholder="например: 08:00,13:30,18:00"
                        />
                        {errors.time && <div className="form-error">{errors.time}</div>}
                    </label>

                    <label>
                        Название календаря
                        <input
                            type="text"
                            value={calendarName}
                            onChange={e => setCalendarName(e.target.value)}
                            placeholder="Например: ВВГУ_Расписание"
                        />
                    </label>

                    <div
                        className={`file-drop-zone ${dragActive ? "drag-active" : ""}`}
                        onClick={() => document.getElementById("fileInput")?.click()}
                    >
                        {file ? `Файл: ${file.name}` : "Перетащите сюда credentials.json или кликните для выбора"}
                        <input
                            type="file"
                            id="fileInput"
                            accept=".json"
                            style={{display: "none"}}
                            onChange={e => setFile(e.target.files?.[0] || null)}
                        />
                    </div>
                    {errors.file && <div className="form-error">{errors.file}</div>}

                    <button type="submit">Сохранить и продолжить</button>
                </form>
            </div>
        </div>
    )
}
