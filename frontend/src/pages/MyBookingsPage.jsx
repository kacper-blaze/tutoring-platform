import { useEffect, useState } from "react";
import { api } from "../api/client";
import { useAuth } from "../context/AuthContext";

const STATUS_LABELS = {
  PENDING_PAYMENT: "Oczekuje płatności",
  CONFIRMED: "Potwierdzona",
  COMPLETED: "Zakończona",
  EXPIRED: "Wygasła",
  CANCELLED_BY_STUDENT: "Anulowana przez Ciebie",
  CANCELLED_BY_TUTOR: "Anulowana przez korepetytora",
  REFUND_PENDING: "Zwrot w toku",
};

export default function MyBookingsPage() {
  const { user } = useAuth();
  const [items, setItems] = useState([]);
  const [loading, setLoading] = useState(true);
  const [actionId, setActionId] = useState(null);
  const [notice, setNotice] = useState(null);

  async function load() {
    setLoading(true);
    try {
      const data = await api.get("/bookings/transactions");
      setItems(data.items);
    } finally {
      setLoading(false);
    }
  }

  useEffect(() => {
    load();
  }, []);

  async function handleCancel(bookingId) {
    setActionId(bookingId);
    setNotice(null);
    try {
      const result = await api.del(`/bookings/${bookingId}`, { reason: "Zmiana planów" });
      setNotice(
        result.refund
          ? `Rezerwacja anulowana. Zwrot ${result.refund.amount.value.toFixed(0)} zł zostanie przetworzony.`
          : "Rezerwacja anulowana."
      );
      await load();
    } catch {
      setNotice("Nie udało się anulować rezerwacji.");
    } finally {
      setActionId(null);
    }
  }

  async function handlePay(bookingId) {
    setActionId(bookingId);
    setNotice(null);
    try {
      await api.post(`/bookings/${bookingId}/payments`, {
        idempotencyKey: `web-retry-${bookingId}-${Date.now()}`,
      });
      await load();
    } catch {
      setNotice("Płatność nie powiodła się.");
    } finally {
      setActionId(null);
    }
  }

  return (
    <div className="page container">
      <div className="hero">
        <div className="hero-eyebrow">Twoje konto</div>
        <h1>Moje rezerwacje</h1>
      </div>

      {notice && <div className="notice">{notice}</div>}

      {loading && <div className="empty-state">Wczytywanie…</div>}

      {!loading && items.length === 0 && (
        <div className="empty-state">Nie masz jeszcze żadnych rezerwacji — przeglądnij katalog ofert.</div>
      )}

      <div className="data-list">
        {items.map((b) => (
          <div key={b.bookingId} className="data-row">
            <div className="data-row-main">
              <span>{b.amount.value.toFixed(0)} zł</span>
              <span style={{ fontSize: "0.82rem", color: "var(--color-ink-faint)" }}>
                {new Date(b.createdAt).toLocaleString("pl-PL")}
              </span>
            </div>
            <span className={`status-tag status-${b.status}`}>{STATUS_LABELS[b.status] || b.status}</span>
            {user?.role === "STUDENT" && (
              <div className="data-row-actions">
                {b.status === "PENDING_PAYMENT" && (
                  <button
                    className="btn btn-teal btn-small"
                    disabled={actionId === b.bookingId}
                    onClick={() => handlePay(b.bookingId)}
                  >
                    Zapłać
                  </button>
                )}
                {(b.status === "PENDING_PAYMENT" || b.status === "CONFIRMED") && (
                  <button
                    className="btn btn-secondary btn-small"
                    disabled={actionId === b.bookingId}
                    onClick={() => handleCancel(b.bookingId)}
                  >
                    Anuluj
                  </button>
                )}
              </div>
            )}
          </div>
        ))}
      </div>
    </div>
  );
}
