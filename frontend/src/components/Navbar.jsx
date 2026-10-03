import { Link, useNavigate } from "react-router-dom";
import { useAuth } from "../context/AuthContext";

export default function Navbar() {
  const { user, logout } = useAuth();
  const navigate = useNavigate();

  function handleLogout() {
    logout();
    navigate("/");
  }

  return (
    <header className="navbar">
      <Link to="/" className="brand">
        <span className="brand-mark">⟶</span> Korepetycje
      </Link>
      <nav className="nav-links">
        <Link to="/">Katalog</Link>
        {user?.role === "TUTOR" && <Link to="/panel-korepetytora">Mój panel</Link>}
        {user?.role === "STUDENT" && <Link to="/moje-rezerwacje">Moje rezerwacje</Link>}
        {user ? (
          <button className="link-button" onClick={handleLogout}>
            Wyloguj ({user.email})
          </button>
        ) : (
          <>
            <Link to="/zaloguj">Zaloguj się</Link>
            <Link to="/rejestracja" className="cta-link">
              Dołącz
            </Link>
          </>
        )}
      </nav>
    </header>
  );
}
