import type {FormEvent} from "react";
import {useNavigate} from "react-router-dom";
import {motion} from "framer-motion";
import {useAuth} from "../context/Auth";
import "../styles/auth-form.css";

export default function Login() {
    const {login} = useAuth();
    const nav = useNavigate();

    const onSubmit = async (e: FormEvent<HTMLFormElement>) => {
        e.preventDefault();
        const fd = new FormData(e.currentTarget);
        const body = {
            username: fd.get("username") as string,
            password: fd.get("password") as string,
        };

        const r = await fetch("/auth/login", {
            method: "POST",
            headers: {"Content-Type": "application/json"},
            body: JSON.stringify(body),
        });

        if (r.ok) {
            const {access_token} = await r.json();
            login(access_token);
            nav("/");
        } else {
            alert("Неверный логин или пароль");
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
                <h1>Вход в систему</h1>

                <input name="username" placeholder="Логин" required/>
                <input
                    name="password"
                    type="password"
                    placeholder="Пароль"
                    required
                />

                <button>Войти</button>
            </motion.form>
        </div>
    );
}
