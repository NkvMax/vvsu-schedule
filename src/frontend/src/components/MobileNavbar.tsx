import {NavLink} from "react-router-dom"
import "../styles/navbar.css"
import homeIcon from "../assets/icons/home.png"
import settingsIcon from "../assets/icons/settings.png"

type Props = {
    active: "home" | "account"
}

export default function MobileNavbar({active}: Props) {
    return (
        <nav className="mobile-nav-island">
            <NavLink to="/home" className={active === "home" ? "active" : ""}>
                <img src={homeIcon} alt="Главная"/>
                <span>Home</span>
            </NavLink>
            <NavLink to="/account" className={active === "account" ? "active" : ""}>
                <img src={settingsIcon} alt="Настройки"/>
                <span>Settings</span>
            </NavLink>
        </nav>
    )
}

