import type {FormEvent} from "react";
import {useNavigate} from "react-router-dom";
import {motion} from "framer-motion";
import {useState} from "react";
import {useAuth} from "../context/Auth";
import "../styles/auth-form.css";

export default function Register() {
    const {login} = useAuth();
    const nav = useNavigate();
    const [err, setErr] = useState("");

    const onSubmit = async (e: FormEvent<HTMLFormElement>) => {
        e.preventDefault();
        setErr("");

        const f = new FormData(e.currentTarget);
        const username = f.get("username") as string;
        const pass1 = f.get("password") as string;
        const pass2 = f.get("password2") as string;

        if (pass1 !== pass2) {
            setErr("Пароли не совпадают");
            return;
        }

        const r = await fetch("/auth/register", {
            method: "POST",
            headers: {"Content-Type": "application/json"},
            body: JSON.stringify({username, password: pass1}),
        });

        if (r.ok) {
            const {access_token} = await r.json();
            login(access_token);
            nav("/", {replace: true});
        } else {
            setErr("Регистрация недоступна (админ уже есть?)");
        }
    };

    return (
        <div className="auth-page">
            <motion.form
                className="auth-card"
                onSubmit={onSubmit}
                initial={{y: 60, opacity: 0}}
                animate={{y: 0, opacity: 1}}
                transition={{type: "spring", stiffness: 70, damping: 14}}
            >
                <h1>Регистрация</h1>

                <input name="username" placeholder="Логин" required/>
                <input name="password" type="password" placeholder="Пароль" required minLength={6}/>
                <input name="password2" type="password" placeholder="Повторите пароль" required/>

                {err && <p className="err-hint">{err}</p>}

                <button>Создать администратора</button>
            </motion.form>
        </div>
    );
}
