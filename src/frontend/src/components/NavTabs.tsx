import {Link} from 'react-router-dom'

type Props = { active: 'home' | 'account' }
export default function NavTabs({active}: Props) {
    return (
        <nav className="flex space-x-4 mb-4">
            <Link to="/home" className={active === 'home' ? 'font-bold' : ''}>Home</Link>
            <Link to="/account" className={active === 'account' ? 'font-bold' : ''}>Account</Link>
        </nav>
    )
}
