import { useState } from "react";
import { Link, useLocation, useNavigate } from "react-router-dom";
import { useAuth } from "../context/AuthContext";
import { ApiError } from "../api/client";

export default function LoginPage() {
  const { login } = useAuth();
  const navigate = useNavigate();
  const location = useLocation();
  const [email, setEmail] = useState("");
  const [password, setPassword] = useState("");
  const [error, setError] = useState(null);
  const [submitting, setSubmitting] = useState(false);

  async function handleSubmit(e) {
    e.preventDefault();
    setSubmitting(true);
    setError(null);
    try {
      const data = await login(email, password);
      const redirectTo = location.state?.from || (data.role === "TUTOR" ? "/panel-korepetytora" : "/");
      navigate(redirectTo, { replace: true });
    } catch (err) {
      if (err instanceof ApiError) {
        if (err.code === "ACCOUNT_TEMPORARILY_LOCKED") {
          setError("Konto zostało tymczasowo zablokowane po zbyt wielu nieudanych próbach logowania.");
        } else if (err.code === "ACCOUNT_NOT_ACTIVATED") {
          setError("Konto nie zostało jeszcze aktywowane — sprawdź link aktywacyjny.");
        } else {
          setError("Nieprawidłowy e-mail lub hasło.");
        }
      } else {
        setError("Nie udało się połączyć z serwerem.");
      }
    } finally {
      setSubmitting(false);
    }
  }

  return (
    <div className="page container">
      <div className="hero">
        <div className="hero-eyebrow">Witaj ponownie</div>
        <h1>Zaloguj się</h1>
      </div>

      <form className="form" onSubmit={handleSubmit}>
        {error && <div className="notice notice-error">{error}</div>}

        <div className="field">
          <label htmlFor="email">E-mail</label>
          <input id="email" type="email" value={email} onChange={(e) => setEmail(e.target.value)} required />
        </div>

        <div className="field">
          <label htmlFor="password">Hasło</label>
          <input
            id="password"
            type="password"
            value={password}
            onChange={(e) => setPassword(e.target.value)}
            required
          />
        </div>

        <button className="btn btn-primary" type="submit" disabled={submitting}>
          {submitting ? "Logowanie…" : "Zaloguj się"}
        </button>
      </form>

      <p style={{ marginTop: "1.5rem" }}>
        Nie masz jeszcze konta? <Link to="/rejestracja">Załóż je</Link>
      </p>
    </div>
  );
}
