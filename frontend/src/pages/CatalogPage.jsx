import { useEffect, useState } from "react";
import { Link } from "react-router-dom";
import { api } from "../api/client";

const SORT_OPTIONS = [
  { value: "newest", label: "Najnowsze" },
  { value: "price_asc", label: "Cena: od najniższej" },
  { value: "price_desc", label: "Cena: od najwyższej" },
  { value: "rating_desc", label: "Najwyżej oceniane" },
];

export default function CatalogPage() {
  const [filters, setFilters] = useState({ keyword: "", subject: "", priceMax: "", sort: "newest" });
  const [offers, setOffers] = useState([]);
  const [total, setTotal] = useState(0);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState(null);

  async function search(activeFilters) {
    setLoading(true);
    setError(null);
    try {
      const data = await api.get("/offers", {
        keyword: activeFilters.keyword || undefined,
        subject: activeFilters.subject || undefined,
        priceMax: activeFilters.priceMax || undefined,
        sort: activeFilters.sort,
        pageSize: 50,
      });
      setOffers(data.items);
      setTotal(data.total);
    } catch {
      setError("Nie udało się pobrać ofert. Czy backend działa na porcie 8000?");
    } finally {
      setLoading(false);
    }
  }

  useEffect(() => {
    search(filters);
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, []);

  function handleFilterSubmit(e) {
    e.preventDefault();
    search(filters);
  }

  return (
    <div className="page container">
      <div className="hero">
        <div className="hero-eyebrow">Katalog ofert</div>
        <h1>Znajdź korepetytora</h1>
        <p>Przeszukaj aktywne oferty po przedmiocie, cenie i słowie kluczowym.</p>
      </div>

      <form className="filters" onSubmit={handleFilterSubmit}>
        <div className="field">
          <label htmlFor="keyword">Słowo kluczowe</label>
          <input
            id="keyword"
            placeholder="np. matematyka"
            value={filters.keyword}
            onChange={(e) => setFilters((f) => ({ ...f, keyword: e.target.value }))}
          />
        </div>
        <div className="field">
          <label htmlFor="priceMax">Cena maks. (zł/h)</label>
          <input
            id="priceMax"
            type="number"
            min="0"
            value={filters.priceMax}
            onChange={(e) => setFilters((f) => ({ ...f, priceMax: e.target.value }))}
          />
        </div>
        <div className="field">
          <label htmlFor="sort">Sortowanie</label>
          <select
            id="sort"
            value={filters.sort}
            onChange={(e) => setFilters((f) => ({ ...f, sort: e.target.value }))}
          >
            {SORT_OPTIONS.map((opt) => (
              <option key={opt.value} value={opt.value}>
                {opt.label}
              </option>
            ))}
          </select>
        </div>
        <button className="btn btn-secondary" type="submit">
          Szukaj
        </button>
      </form>

      {error && <div className="notice notice-error">{error}</div>}

      {!loading && !error && (
        <p style={{ color: "var(--color-ink-faint)", fontSize: "0.88rem" }}>
          {total} {total === 1 ? "oferta" : "ofert"} spełnia kryteria
        </p>
      )}

      <div className="offer-list">
        {loading && <div className="empty-state">Wczytywanie ofert…</div>}
        {!loading && offers.length === 0 && !error && (
          <div className="empty-state">
            Brak ofert spełniających te kryteria. Spróbuj poszerzyć wyszukiwanie.
          </div>
        )}
        {offers.map((offer) => (
          <Link key={offer.offerId} to={`/korepetytorzy/${offer.tutorId}`} className="offer-row">
            <div className="offer-main">
              <span className="offer-subject">{offer.subject}</span>
              <span className="offer-tutor">{offer.tutorName}</span>
            </div>
            <div className="offer-meta">
              <span className="offer-rating">
                {offer.reviewCount > 0 ? `★ ${offer.averageRating.toFixed(1)} (${offer.reviewCount})` : "Brak opinii"}
              </span>
              <span className="offer-price">{offer.hourlyRate.toFixed(0)} zł/h</span>
            </div>
          </Link>
        ))}
      </div>
    </div>
  );
}
