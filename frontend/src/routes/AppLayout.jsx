import React, { useContext, useState } from "react";
import { Link, Routes, Route, useLocation, useNavigate } from "react-router-dom";
import ChatPage from "./ChatPage.jsx";
import DocumentsPage from "./DocumentsPage.jsx";
import SettingsPage from "./SettingsPage.jsx";
import GeneralSettingsPage from "./GeneralSettingsPage.jsx";
import ToolsPage from "./ToolsPage.jsx";
import { UserContext } from "../App.jsx";
import { useOrganization } from "../contexts/OrganizationContext.jsx";

const AppLayout = () => {
  const { user, setUser } = useContext(UserContext);
  const { organizationName } = useOrganization();
  const location = useLocation();
  const navigate = useNavigate();
  const [sidebarOpen, setSidebarOpen] = useState(false);

  const isActive = (path) => location.pathname.startsWith(path);

  const handleLogout = async () => {
    try {
      // Call logout endpoint if it exists
      await fetch(`${import.meta.env.VITE_BACKEND_BASE_URL || "http://localhost:8000"}/auth/logout`, {
        method: "POST",
        credentials: "include",
      }).catch(() => {
        // Ignore if endpoint doesn't exist
      });
    } finally {
      setUser(null);
      navigate("/login", { replace: true });
    }
  };

  const navItems = [
    { path: "/app/chat", label: "Chat", icon: "💬" },
    { path: "/app/documents", label: "Documents", icon: "📄" },
    { path: "/app/tools", label: "Tools", icon: "🔧" },
    { path: "/app/general-settings", label: "General Settings", icon: "👤" },
    { path: "/app/settings", label: "LLM Settings", icon: "⚙️" },
  ];

  return (
    <div style={{ display: "flex", minHeight: "100vh", background: "var(--bg-secondary)" }}>
      {/* Mobile Menu Overlay */}
      {sidebarOpen && (
        <div
          onClick={() => setSidebarOpen(false)}
          style={{
            position: "fixed",
            inset: 0,
            background: "rgba(0, 0, 0, 0.5)",
            zIndex: 40,
            display: "block",
          }}
          className="mobile-overlay"
        />
      )}

      {/* Sidebar */}
      <aside
        className={`sidebar ${sidebarOpen ? "sidebar-open" : ""}`}
        style={{
          width: "280px",
          background: "var(--bg-sidebar)",
          color: "var(--text-inverse)",
          padding: "var(--spacing-xl)",
          display: "flex",
          flexDirection: "column",
          position: "fixed",
          height: "100vh",
          zIndex: 50,
          transition: "transform var(--transition-slow) cubic-bezier(0.4, 0, 0.2, 1)",
          boxShadow: "var(--shadow-lg)",
        }}
      >
        {/* Mobile Close Button */}
        <button
          onClick={() => setSidebarOpen(false)}
          style={{
            display: "none",
            position: "absolute",
            top: "1rem",
            right: "1rem",
            background: "transparent",
            border: "none",
            color: "var(--text-inverse)",
            fontSize: "1.5rem",
            cursor: "pointer",
            padding: "0.5rem",
          }}
          className="mobile-close-btn"
        >
          ✕
        </button>

        {/* Logo/Title */}
        <div className="fade-in-down" style={{ marginBottom: "var(--spacing-xl)" }}>
          <h1
            style={{
              fontSize: "1.5rem",
              fontWeight: 700,
              marginBottom: "var(--spacing-sm)",
              color: "var(--text-inverse)",
            }}
          >
            {organizationName} Assistant
          </h1>
          {user && (
            <div
              style={{
                fontSize: "0.875rem",
                color: "var(--gray-400)",
                display: "flex",
                alignItems: "center",
                gap: "var(--spacing-sm)",
              }}
            >
              {user.picture ? (
                <>
                  <img
                    src={user.picture}
                    alt="Profile"
                    style={{
                      width: "32px",
                      height: "32px",
                      borderRadius: "50%",
                      objectFit: "cover",
                      border: "2px solid var(--gray-600)",
                      display: "inline-block",
                    }}
                    onError={(e) => {
                      // Hide image and show fallback on error (429, 404, etc.)
                      e.target.style.display = "none";
                      const fallback = e.target.parentElement?.querySelector('.profile-fallback');
                      if (fallback) {
                        fallback.style.display = "inline-block";
                      }
                    }}
                    loading="lazy"
                    referrerPolicy="no-referrer"
                  />
                  <span
                    className="profile-fallback"
                    style={{
                      width: "32px",
                      height: "32px",
                      borderRadius: "50%",
                      background: "var(--gray-600)",
                      display: "none",
                      fontSize: "0.75rem",
                      color: "var(--text-inverse)",
                      lineHeight: "32px",
                      textAlign: "center",
                      fontWeight: 600,
                    }}
                  >
                    {user.name ? user.name.charAt(0).toUpperCase() : "U"}
                  </span>
                </>
              ) : (
                <span
                  style={{
                    width: "32px",
                    height: "32px",
                    borderRadius: "50%",
                    background: "var(--gray-600)",
                    display: "inline-flex",
                    alignItems: "center",
                    justifyContent: "center",
                    fontSize: "0.75rem",
                    color: "var(--text-inverse)",
                    fontWeight: 600,
                  }}
                >
                  {user.name ? user.name.charAt(0).toUpperCase() : "U"}
                </span>
              )}
              <span
                style={{
                  width: "8px",
                  height: "8px",
                  borderRadius: "50%",
                  background: "var(--success)",
                  display: user.picture ? "none" : "inline-block",
                }}
              />
              {(() => {
                const displayName = user.name || user.email || "";
                // Format to UCfirst: first letter uppercase, rest lowercase
                const formattedName = displayName
                  .split(" ")
                  .map(word => word.charAt(0).toUpperCase() + word.slice(1).toLowerCase())
                  .join(" ");
                return formattedName;
              })()}
              {user.provider && (
                <span style={{ color: "var(--gray-500)", textTransform: "uppercase", fontSize: "0.75rem" }}>
                  ({user.provider})
                </span>
              )}
            </div>
          )}
        </div>

        {/* Navigation */}
        <nav style={{ display: "flex", flexDirection: "column", gap: "var(--spacing-xs)", flex: 1 }}>
          {navItems.map((item, index) => {
            const active = isActive(item.path);
            return (
              <Link
                key={item.path}
                to={item.path}
                onClick={() => setSidebarOpen(false)}
                className="fade-in-left"
                style={{
                  display: "flex",
                  alignItems: "center",
                  gap: "var(--spacing-md)",
                  padding: "var(--spacing-md)",
                  borderRadius: "var(--radius-md)",
                  color: active ? "var(--text-inverse)" : "var(--gray-400)",
                  background: active ? "var(--bg-sidebar-hover)" : "transparent",
                  textDecoration: "none",
                  fontWeight: active ? 500 : 400,
                  transition: "all var(--transition-base)",
                  animationDelay: `${index * 0.1}s`,
                  transform: active ? "translateX(4px)" : "translateX(0)",
                }}
                onMouseEnter={(e) => {
                  if (!active) {
                    e.currentTarget.style.background = "var(--bg-sidebar-hover)";
                    e.currentTarget.style.color = "var(--text-inverse)";
                    e.currentTarget.style.transform = "translateX(4px)";
                  }
                }}
                onMouseLeave={(e) => {
                  if (!active) {
                    e.currentTarget.style.background = "transparent";
                    e.currentTarget.style.color = "var(--gray-400)";
                    e.currentTarget.style.transform = "translateX(0)";
                  }
                }}
              >
                <span style={{ fontSize: "1.25rem", transition: "transform var(--transition-base)" }}>
                  {item.icon}
                </span>
                <span>{item.label}</span>
              </Link>
            );
          })}
        </nav>

        {/* Logout Button */}
        <button
          onClick={handleLogout}
          className="btn btn-secondary fade-in-up"
          style={{
            marginTop: "auto",
            width: "100%",
            background: "var(--error)",
            color: "var(--text-inverse)",
            animationDelay: "0.3s",
          }}
        >
          Logout
        </button>
      </aside>

      {/* Main Content */}
      <main
        style={{
          flex: 1,
          marginLeft: "280px",
          minHeight: "100vh",
          background: "var(--bg-secondary)",
        }}
        className="main-content"
      >
        {/* Mobile Header */}
        <div
          style={{
            display: "none",
            padding: "var(--spacing-md)",
            background: "var(--bg-primary)",
            borderBottom: "1px solid var(--gray-200)",
            alignItems: "center",
            gap: "var(--spacing-md)",
          }}
          className="mobile-header"
        >
          <button
            onClick={() => setSidebarOpen(true)}
            style={{
              background: "transparent",
              border: "none",
              fontSize: "1.5rem",
              cursor: "pointer",
              padding: "var(--spacing-sm)",
            }}
          >
            ☰
          </button>
          <h1 style={{ fontSize: "1.25rem", fontWeight: 600 }}>Anukara</h1>
        </div>

        <div style={{ padding: "var(--spacing-xl)", maxWidth: "1200px", margin: "0 auto" }}>
          <Routes>
            <Route path="chat" element={<ChatPage />} />
            <Route path="documents" element={<DocumentsPage />} />
            <Route path="tools" element={<ToolsPage />} />
            <Route path="general-settings" element={<GeneralSettingsPage />} />
            <Route path="settings" element={<SettingsPage />} />
          </Routes>
        </div>
      </main>

      <style>{`
        @media (max-width: 768px) {
          .sidebar {
            transform: translateX(-100%);
          }
          .sidebar-open {
            transform: translateX(0);
          }
          .main-content {
            margin-left: 0 !important;
          }
          .mobile-header {
            display: flex !important;
            animation: fadeInDown 0.3s ease-out;
          }
          .mobile-close-btn {
            display: block !important;
            transition: transform var(--transition-base);
          }
          .mobile-close-btn:hover {
            transform: rotate(90deg);
          }
          .mobile-overlay {
            animation: fadeIn 0.3s ease-out;
          }
        }
      `}</style>
    </div>
  );
};

export default AppLayout;
