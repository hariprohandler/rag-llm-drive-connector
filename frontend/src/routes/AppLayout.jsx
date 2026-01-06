import React, { useContext } from "react";
import { Link, Routes, Route, useLocation, useNavigate } from "react-router-dom";
import ChatPage from "./ChatPage.jsx";
import DocumentsPage from "./DocumentsPage.jsx";
import SettingsPage from "./SettingsPage.jsx";
import { UserContext } from "../App.jsx";

const AppLayout = () => {
  const { user, setUser } = useContext(UserContext);
  const location = useLocation();
  const navigate = useNavigate();

  const isActive = (path) => location.pathname.startsWith(path);

  const handleLogout = () => {
    // For now, just clear user on frontend; you can add /auth/logout later.
    setUser(null);
    navigate("/login", { replace: true });
  };

  return (
    <div style={{ display: "flex", minHeight: "100vh" }}>
      <aside
        style={{
          width: 260,
          background: "linear-gradient(180deg, #1a1a1a 0%, #2d2d2d 100%)",
          color: "#fff",
          padding: 20
        }}
      >
        <h2>RAG Chat Platform</h2>
        <div style={{ marginBottom: 16, fontSize: 14 }}>
          {user
            ? `${user.name || user.email} (${(user.provider || "demo").toUpperCase()})`
            : "Not signed in"}
        </div>
        <nav style={{ display: "flex", flexDirection: "column", gap: 8 }}>
          <Link
            to="/app/chat"
            style={{ color: isActive("/app/chat") ? "#fff" : "#ccc", textDecoration: "none" }}
          >
            💬 Chat
          </Link>
          <Link
            to="/app/documents"
            style={{ color: isActive("/app/documents") ? "#fff" : "#ccc", textDecoration: "none" }}
          >
            📄 Documents
          </Link>
          <Link
            to="/app/settings"
            style={{ color: isActive("/app/settings") ? "#fff" : "#ccc", textDecoration: "none" }}
          >
            ⚙️ LLM Settings
          </Link>
        </nav>
        <button
          onClick={handleLogout}
          style={{ marginTop: 24, padding: "6px 12px", fontSize: 14 }}
        >
          Logout
        </button>
      </aside>
      <main style={{ flex: 1, padding: 24, background: "#f5f5f5" }}>
        <Routes>
          <Route path="chat" element={<ChatPage />} />
          <Route path="documents" element={<DocumentsPage />} />
          <Route path="settings" element={<SettingsPage />} />
        </Routes>
      </main>
    </div>
  );
};

export default AppLayout;


