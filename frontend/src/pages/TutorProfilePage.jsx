import { useEffect, useState } from "react";
import { useNavigate, useParams } from "react-router-dom";
import { api, ApiError } from "../api/client";
import { useAuth } from "../context/AuthContext";

function formatDate(iso) {
  const d = new Date(iso);
  return d.toLocaleDateString("pl-PL", { weekday: "short", day: "2-digit", month: "short" });
}
function formatTime(iso) {
  const d = new Date(iso);
  return d.toLocaleTimeString("pl-PL", { hour: "2-digit", minute: "2-digit" });
}

export default function TutorProfilePage() {
  const { tutorId } = useParams();
  const { user } = useAuth();
  const navigate = useNavigate();

  const [profile, setProfile] = useState(null);
  const [reviews, setReviews] = useState([]);
  const [slots, setSlots] = useState([]);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState(null);

  const [selectedSlot, setSelectedSlot] = useState(null);
  const [booking, setBooking] = useState(null); // { bookingId, status, amount }
  const [bookingError, setBookingError] = useState(null);
  const [actionLoading, setActionLoading] = useState(false);

  useEffect(() => {
    async function load() {
      setLoading(true);
      setError(null);
      try {
        const today = new Date();
        const to = new Date();
        to.setDate(to.getDate() + 21);
        const fmt = (d) => d.toISOString().slice(0, 10);

        const [profileData, reviewsData, slotsData] = await Promise.all([
          api.get(`/tutors/${tutorId}`),
          api.get(`/tutors/${tutorId}/reviews`),
          api.get(`/tutors/${tutorId}/slots`, { from: fmt(today), to: fmt(to) }),
        ]);
        setProfile(profileData);
        setReviews(reviewsData.items);
        setSlots(slotsData.slots);
      } catch {
        setError("Nie udało się wczytać profilu korepetytora.");
      } finally {
        setLoading(false);
      }
    }
    load();
  }, [tutorId]);

  async function handleBook() {
    if (!user) {
      navigate("/zaloguj", { state: { from: `/korepetytorzy/${tutorId}` } });
      return;
    }
    if (!selectedSlot) return;
    setActionLoading(true);
    setBookingError(null);
    try {
      const data = await api.post("/bookings", { slotId: selectedSlot.slotId });
      setBooking(data);
    } catch (err) {
      if (err instanceof ApiError && err.code === "SLOT_UNAVAILABLE") {
        setBookingError("Ups, ten termin został właśnie zajęty przez kogoś innego. Wybierz inny.");
        setSlots((prev) => prev.filter((s) => s.slotId !== selectedSlot.slotId));
        setSelectedSlot(null);
      } else {
        setBookingError("Nie udało się utworzyć rezerwacji.");
      }
    } finally {
      setActionLoading(false);
    }
  }

  async function handlePay() {
    if (!booking) return;
    setActionLoading(true);
    setBookingError(null);
    try {
      const idempotencyKey = `web-${booking.bookingId}-${Date.now()}`;
      const data = await api.post(`/bookings/${booking.bookingId}/payments`, { idempotencyKey });
      setBooking(data);
      if (data.status === "CONFIRMED") {
        setTimeout(() => navigate("/moje-rezerwacje"), 1200);
      }
    } catch {
      setBookingError("Płatność nie powiodła się. Spróbuj ponownie.");
    } finally {
      setActionLoading(false);
    }
  }

  if (loading) return <div className="page container page-loading">Wczytywanie profilu…</div>;
  if (error || !profile) return <div className="page container notice notice-error">{error}</div>;

  const initials = `${profile.firstName[0]}${profile.lastName[0]}`;

  return (
    <div className="page container">
      <div className="tutor-header">
        <div className="avatar-placeholder">{initials}</div>
        <div>
          <h1 style={{ marginBottom: "0.2rem" }}>
            {profile.firstName} {profile.lastName}
          </h1>
          <div style={{ marginBottom: "0.5rem" }}>
            {profile.reviewCount > 0 ? (
              <span className="badge badge-amber">
                ★ {profile.averageRating.toFixed(1)} · {profile.reviewCount}{" "}
                {profile.reviewCount === 1 ? "opinia" : "opinii"}
              </span>
            ) : (
              <span className="badge badge-teal">Nowy korepetytor</span>
            )}
          </div>
          {profile.bio && <p>{profile.bio}</p>}
        </div>
      </div>

      <div className="section">
        <h2>Oferty</h2>
        <div className="offer-chip-list">
          {profile.offers.map((o) => (
            <span key={o.id} className="offer-chip">
              {o.subject} — {o.hourlyRate.toFixed(0)} zł/h
            </span>
          ))}
          {profile.offers.length === 0 && <p>Ten korepetytor nie ma jeszcze aktywnych ofert.</p>}
        </div>
      </div>

      <div className="section">
        <h2>Dostępne terminy</h2>
        {slots.length === 0 ? (
          <p>Brak wolnych terminów w najbliższych trzech tygodniach.</p>
        ) : (
          <div className="slot-grid">
            {slots.map((slot) => (
              <button
                key={slot.slotId}
                type="button"
                className={`slot-btn ${selectedSlot?.slotId === slot.slotId ? "selected" : ""}`}
                onClick={() => {
                  setSelectedSlot(slot);
                  setBooking(null);
                  setBookingError(null);
                }}
              >
                <span className="slot-date">{formatDate(slot.startTime)}</span>
                <span className="slot-time">{formatTime(slot.startTime)}</span>
              </button>
            ))}
          </div>
        )}

        {selectedSlot && !booking && (
          <div style={{ marginTop: "1.4rem" }}>
            {bookingError && <div className="notice notice-error">{bookingError}</div>}
            <button className="btn btn-primary" onClick={handleBook} disabled={actionLoading}>
              {actionLoading
                ? "Rezerwowanie…"
                : `Zarezerwuj termin ${formatDate(selectedSlot.startTime)}, ${formatTime(selectedSlot.startTime)}`}
            </button>
          </div>
        )}

        {booking && booking.status === "PENDING_PAYMENT" && (
          <div className="notice" style={{ marginTop: "1.4rem" }}>
            <p style={{ marginBottom: "0.8rem" }}>
              Rezerwacja utworzona — kwota <strong>{booking.amount.value.toFixed(0)} zł</strong>. Masz 15 minut
              na opłacenie, zanim termin zostanie zwolniony.
            </p>
            {bookingError && <div className="notice notice-error">{bookingError}</div>}
            <button className="btn btn-teal" onClick={handlePay} disabled={actionLoading}>
              {actionLoading ? "Przetwarzanie płatności…" : "Zapłać teraz"}
            </button>
          </div>
        )}

        {booking && booking.status === "CONFIRMED" && (
          <div className="notice notice-success" style={{ marginTop: "1.4rem" }}>
            Płatność zaakceptowana, termin potwierdzony! Przenosimy Cię do Twoich rezerwacji…
          </div>
        )}
      </div>

      <div className="section">
        <h2>Opinie</h2>
        {reviews.length === 0 && <p>Ten korepetytor nie ma jeszcze opinii.</p>}
        {reviews.map((r) => (
          <div key={r.id} className="review-item">
            <span className="review-rating">{"★".repeat(r.rating)}</span>
            <span className="review-date">{new Date(r.createdAt).toLocaleDateString("pl-PL")}</span>
            {r.comment && <p style={{ marginTop: "0.3rem" }}>{r.comment}</p>}
          </div>
        ))}
      </div>
    </div>
  );
}
