import {NavLink} from "react-router-dom"
import "../styles/navbar.css"

export default function Navigation() {
    return (
        <nav className="nav-wrapper">
            <ul className="nav-list">
                <li>
                    <NavLink
                        to="/home"
                        className={({isActive}) => (isActive ? "nav-link active" : "nav-link")}
                    >
                        Центр&nbsp;управления
                    </NavLink>
                </li>
                <li>
                    <NavLink
                        to="/account"
                        className={({isActive}) => (isActive ? "nav-link active" : "nav-link")}
                    >
                        Редактировать&nbsp;данные
                    </NavLink>
                </li>
            </ul>
        </nav>
    )
}
