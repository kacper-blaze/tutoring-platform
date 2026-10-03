import { useEffect, useState } from "react";
import { api, ApiError } from "../api/client";
import { useAuth } from "../context/AuthContext";

const DAYS = ["Poniedziałek", "Wtorek", "Środa", "Czwartek", "Piątek", "Sobota", "Niedziela"];

function todayIso() {
  return new Date().toISOString().slice(0, 10);
}

export default function TutorDashboardPage() {
  const { user } = useAuth();
  const [offers, setOffers] = useState([]);
  const [offerForm, setOfferForm] = useState({ subject: "", hourlyRate: "" });
  const [offerError, setOfferError] = useState(null);
  const [offerSubmitting, setOfferSubmitting] = useState(false);

  const [rules, setRules] = useState([{ dayOfWeek: 0, startTime: "10:00", endTime: "14:00", validFrom: todayIso() }]);
  const [availabilityResult, setAvailabilityResult] = useState(null);
  const [availabilityError, setAvailabilityError] = useState(null);
  const [availabilitySubmitting, setAvailabilitySubmitting] = useState(false);

  async function loadOffers() {
    if (!user) return;
    try {
      const profile = await api.get(`/tutors/${user.id}`);
      setOffers(profile.offers);
    } catch {
      // Profil jeszcze nie istnieje (brak ofert) - katalog zwróci 404 dopóki nie ma pierwszej oferty.
      setOffers([]);
    }
  }

  useEffect(() => {
    loadOffers();
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [user]);

  async function handleCreateOffer(e) {
    e.preventDefault();
    setOfferSubmitting(true);
    setOfferError(null);
    try {
      await api.post("/tutors/me/offers", {
        subject: offerForm.subject,
        hourlyRate: Number(offerForm.hourlyRate),
      });
      setOfferForm({ subject: "", hourlyRate: "" });
      await loadOffers();
    } catch (err) {
      setOfferError(err instanceof ApiError ? err.message : "Nie udało się dodać oferty.");
    } finally {
      setOfferSubmitting(false);
    }
  }

  function updateRule(index, field, value) {
    setRules((prev) => prev.map((r, i) => (i === index ? { ...r, [field]: value } : r)));
  }

  function addRule() {
    setRules((prev) => [...prev, { dayOfWeek: 0, startTime: "10:00", endTime: "14:00", validFrom: todayIso() }]);
  }

  function removeRule(index) {
    setRules((prev) => prev.filter((_, i) => i !== index));
  }

  async function handleSaveAvailability(e) {
    e.preventDefault();
    setAvailabilitySubmitting(true);
    setAvailabilityError(null);
    setAvailabilityResult(null);
    try {
      const payload = {
        rules: rules.map((r) => ({
          dayOfWeek: Number(r.dayOfWeek),
          startTime: `${r.startTime}:00`,
          endTime: `${r.endTime}:00`,
          validFrom: r.validFrom,
        })),
      };
      const data = await api.put("/schedules/me/availability", payload);
      setAvailabilityResult(data);
    } catch (err) {
      setAvailabilityError(err instanceof ApiError ? err.message : "Nie udało się zapisać grafiku.");
    } finally {
      setAvailabilitySubmitting(false);
    }
  }

  return (
    <div className="page container">
      <div className="hero">
        <div className="hero-eyebrow">Panel korepetytora</div>
        <h1>Zarządzaj swoją ofertą</h1>
        <p>Publikuj przedmioty, które uczysz, i ustaw godziny, w których jesteś dostępny.</p>
      </div>

      <div className="panel-grid">
        <div className="panel">
          <h2>Twoje oferty</h2>
          <div className="offer-chip-list" style={{ marginBottom: "1.2rem" }}>
            {offers.length === 0 && <p>Nie masz jeszcze żadnej oferty.</p>}
            {offers.map((o) => (
              <span key={o.id} className="offer-chip">
                {o.subject} — {o.hourlyRate.toFixed(0)} zł/h
              </span>
            ))}
          </div>

          <form className="form" onSubmit={handleCreateOffer}>
            {offerError && <div className="notice notice-error">{offerError}</div>}
            <div className="field">
              <label htmlFor="subject">Przedmiot</label>
              <input
                id="subject"
                placeholder="np. matematyka"
                value={offerForm.subject}
                onChange={(e) => setOfferForm((f) => ({ ...f, subject: e.target.value }))}
                required
              />
            </div>
            <div className="field">
              <label htmlFor="hourlyRate">Stawka (zł/h)</label>
              <input
                id="hourlyRate"
                type="number"
                min="1"
                step="1"
                value={offerForm.hourlyRate}
                onChange={(e) => setOfferForm((f) => ({ ...f, hourlyRate: e.target.value }))}
                required
              />
            </div>
            <button className="btn btn-primary" type="submit" disabled={offerSubmitting}>
              {offerSubmitting ? "Dodawanie…" : "Dodaj ofertę"}
            </button>
          </form>
        </div>

        <div className="panel">
          <h2>Twoja dostępność</h2>
          <p>Zdefiniuj powtarzające się bloki godzinowe — system wygeneruje terminy na najbliższe 4 tygodnie.</p>

          <form className="form form-wide" onSubmit={handleSaveAvailability}>
            {availabilityError && <div className="notice notice-error">{availabilityError}</div>}
            {availabilityResult && (
              <div className="notice notice-success">
                Zapisano. Wygenerowano {availabilityResult.generatedSlots} terminów do{" "}
                {availabilityResult.horizon}.
              </div>
            )}

            {rules.map((rule, i) => (
              <div className="availability-row" key={i}>
                <select value={rule.dayOfWeek} onChange={(e) => updateRule(i, "dayOfWeek", e.target.value)}>
                  {DAYS.map((label, idx) => (
                    <option key={idx} value={idx}>
                      {label}
                    </option>
                  ))}
                </select>
                <input
                  type="time"
                  value={rule.startTime}
                  onChange={(e) => updateRule(i, "startTime", e.target.value)}
                />
                <span>–</span>
                <input type="time" value={rule.endTime} onChange={(e) => updateRule(i, "endTime", e.target.value)} />
                {rules.length > 1 && (
                  <button type="button" className="link-button" onClick={() => removeRule(i)}>
                    Usuń
                  </button>
                )}
              </div>
            ))}

            <button type="button" className="btn btn-secondary btn-small" onClick={addRule} style={{ marginBottom: "1rem" }}>
              + Dodaj kolejny blok
            </button>
            <br />
            <button className="btn btn-primary" type="submit" disabled={availabilitySubmitting}>
              {availabilitySubmitting ? "Zapisywanie…" : "Zapisz dostępność"}
            </button>
          </form>
        </div>
      </div>
    </div>
  );
}
