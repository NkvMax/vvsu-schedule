import {BrowserRouter, Routes, Route, Navigate, Outlet} from "react-router-dom";
import {AuthProvider, useAuth} from "./context/Auth";

import InitGate from "./pages/InitGate";
import RegisterPage from "./pages/Register";
import LoginPage from "./pages/Login";
import HomePage from "./pages/HomePage";
import AccountPage from "./pages/AccountPage";
import SetupWizard from "./pages/SetupWizard";

function PrivateOutlet() {
    const {token} = useAuth();
    return token ? <Outlet/> : <Navigate to="/login" replace/>;
}

export default function App() {
    return (
        <AuthProvider>
            <BrowserRouter>
                <Routes>
                    {/* корневой маршрут: InitGate решает, куда направить */}
                    <Route element={<InitGate/>}>
                        <Route element={<PrivateOutlet/>}>
                            <Route path="/" element={<HomePage/>}/>
                            <Route path="/account" element={<AccountPage/>}/>
                        </Route>
                    </Route>

                    {/* публичные страницы */}
                    <Route path="/register" element={<RegisterPage/>}/>
                    <Route path="/login" element={<LoginPage/>}/>
                    <Route path="/setup" element={<SetupWizard/>}/>

                    {/* fallback */}
                    <Route path="*" element={<Navigate to="/" replace/>}/>
                </Routes>
            </BrowserRouter>
        </AuthProvider>
    );
}
