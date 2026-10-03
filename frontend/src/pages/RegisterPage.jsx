import { useState } from "react";
import { Link, useNavigate } from "react-router-dom";
import { api, ApiError } from "../api/client";

export default function RegisterPage() {
  const navigate = useNavigate();
  const [form, setForm] = useState({
    firstName: "",
    lastName: "",
    email: "",
    password: "",
    role: "STUDENT",
  });
  const [errors, setErrors] = useState({});
  const [submitting, setSubmitting] = useState(false);
  const [done, setDone] = useState(false);

  function update(field, value) {
    setForm((f) => ({ ...f, [field]: value }));
  }

  async function handleSubmit(e) {
    e.preventDefault();
    setSubmitting(true);
    setErrors({});
    try {
      await api.post("/auth/register", form, { auth: false });
      setDone(true);
    } catch (err) {
      if (err instanceof ApiError) {
        const fieldErrors = {};
        for (const d of err.details) fieldErrors[d.field] = d.message || d.code;
        if (Object.keys(fieldErrors).length) {
          setErrors(fieldErrors);
        } else {
          setErrors({ _general: err.message });
        }
      } else {
        setErrors({ _general: "Nie udało się połączyć z serwerem." });
      }
    } finally {
      setSubmitting(false);
    }
  }

  if (done) {
    return (
      <div className="page container">
        <div className="hero">
          <div className="hero-eyebrow">Krok 1 z 2</div>
          <h1>Sprawdź skrzynkę pocztową</h1>
          <p>
            Konto <strong>{form.email}</strong> zostało utworzone. Wysłaliśmy link aktywacyjny — w tym
            środowisku deweloperskim token aktywacyjny znajdziesz bezpośrednio w tabeli{" "}
            <code>user_accounts</code> (kolumna <code>activation_token</code>), dopóki nie podłączono
            prawdziwego dostawcy e-mail.
          </p>
          <Link to="/zaloguj" className="btn btn-secondary">
            Przejdź do logowania
          </Link>
        </div>
      </div>
    );
  }

  return (
    <div className="page container">
      <div className="hero">
        <div className="hero-eyebrow">Dołącz do platformy</div>
        <h1>Załóż konto</h1>
        <p>Jako uczeń znajdziesz korepetytora, jako korepetytor opublikujesz swoje oferty.</p>
      </div>

      <form className="form" onSubmit={handleSubmit}>
        {errors._general && <div className="notice notice-error">{errors._general}</div>}

        <div className="field">
          <label htmlFor="role">Chcę zarejestrować się jako</label>
          <select id="role" value={form.role} onChange={(e) => update("role", e.target.value)}>
            <option value="STUDENT">Uczeń — szukam korepetytora</option>
            <option value="TUTOR">Korepetytor — chcę uczyć</option>
          </select>
        </div>

        <div className="field-row">
          <div className="field">
            <label htmlFor="firstName">Imię</label>
            <input
              id="firstName"
              value={form.firstName}
              onChange={(e) => update("firstName", e.target.value)}
              required
            />
            {errors.firstName && <div className="field-hint">{errors.firstName}</div>}
          </div>
          <div className="field">
            <label htmlFor="lastName">Nazwisko</label>
            <input
              id="lastName"
              value={form.lastName}
              onChange={(e) => update("lastName", e.target.value)}
              required
            />
            {errors.lastName && <div className="field-hint">{errors.lastName}</div>}
          </div>
        </div>

        <div className="field">
          <label htmlFor="email">E-mail</label>
          <input
            id="email"
            type="email"
            value={form.email}
            onChange={(e) => update("email", e.target.value)}
            required
          />
          {errors.email && <div className="field-hint">{errors.email}</div>}
        </div>

        <div className="field">
          <label htmlFor="password">Hasło</label>
          <input
            id="password"
            type="password"
            value={form.password}
            onChange={(e) => update("password", e.target.value)}
            required
          />
          <div className="field-hint">Min. 8 znaków, co najmniej jedna cyfra i jeden znak specjalny.</div>
          {errors.password && <div className="field-hint">{errors.password}</div>}
        </div>

        <button className="btn btn-primary" type="submit" disabled={submitting}>
          {submitting ? "Tworzenie konta…" : "Załóż konto"}
        </button>
      </form>

      <p style={{ marginTop: "1.5rem" }}>
        Masz już konto? <Link to="/zaloguj">Zaloguj się</Link>
      </p>
    </div>
  );
}
