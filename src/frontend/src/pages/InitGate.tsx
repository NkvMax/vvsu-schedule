import {useEffect, useState} from "react";
import {Navigate, Outlet} from "react-router-dom";
import {useAuth} from "../context/Auth";

export default function InitGate() {
    const {token} = useAuth();
    const [needsInit, setNeedsInit] = useState<boolean | null>(null);

    /* один запрос к /auth/needs_init */
    useEffect(() => {
        fetch("/auth/needs_init")
            .then(r => r.json())
            .then(setNeedsInit)
            .catch(() => setNeedsInit(false));
    }, []);

    /* ожидание ответа */
    if (needsInit === null) return <>Загрузка…</>;

    /* таблица admins пуста -> страница регистрации */
    if (needsInit) return <Navigate to="/register" replace/>;

    /* админ уже есть, но токена нет -> страница логина */
    if (!token) return <Navigate to="/login" replace/>;

    /* окен валиден -> рендерим защищенные вложенные маршруты */
    return <Outlet/>;
}
