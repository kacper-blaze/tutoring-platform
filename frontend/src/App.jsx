import { Route, Routes } from "react-router-dom";
import Navbar from "./components/Navbar";
import ProtectedRoute from "./components/ProtectedRoute";
import CatalogPage from "./pages/CatalogPage";
import LoginPage from "./pages/LoginPage";
import RegisterPage from "./pages/RegisterPage";
import TutorProfilePage from "./pages/TutorProfilePage";
import MyBookingsPage from "./pages/MyBookingsPage";
import TutorDashboardPage from "./pages/TutorDashboardPage";

export default function App() {
  return (
    <div className="app-shell">
      <Navbar />
      <Routes>
        <Route path="/" element={<CatalogPage />} />
        <Route path="/zaloguj" element={<LoginPage />} />
        <Route path="/rejestracja" element={<RegisterPage />} />
        <Route path="/korepetytorzy/:tutorId" element={<TutorProfilePage />} />
        <Route
          path="/moje-rezerwacje"
          element={
            <ProtectedRoute requireRole="STUDENT">
              <MyBookingsPage />
            </ProtectedRoute>
          }
        />
        <Route
          path="/panel-korepetytora"
          element={
            <ProtectedRoute requireRole="TUTOR">
              <TutorDashboardPage />
            </ProtectedRoute>
          }
        />
        <Route path="*" element={<NotFound />} />
      </Routes>
      <footer className="footer">System zarządzania platformą korepetycji online — frontend demonstracyjny</footer>
    </div>
  );
}

function NotFound() {
  return (
    <div className="page container">
      <h1>Strona nie istnieje</h1>
      <p>Sprawdź adres albo wróć do katalogu.</p>
    </div>
  );
}
