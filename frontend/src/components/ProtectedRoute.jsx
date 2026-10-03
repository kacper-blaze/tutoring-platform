import { Navigate } from "react-router-dom";
import { useAuth } from "../context/AuthContext";

export default function ProtectedRoute({ children, requireRole }) {
  const { user, loading } = useAuth();

  if (loading) return <div className="page-loading">Wczytywanie…</div>;
  if (!user) return <Navigate to="/zaloguj" replace />;
  if (requireRole && user.role !== requireRole) {
    return (
      <div className="notice notice-error">
        Ta strona jest dostępna wyłącznie dla roli {requireRole === "TUTOR" ? "korepetytora" : "ucznia"}.
      </div>
    );
  }
  return children;
}
