import React, { useEffect, useState } from "react";
import { Routes, Route, Navigate, useLocation } from "react-router-dom";
import { api } from "./api.js";
import LoginPage from "./routes/LoginPage.jsx";
import AppLayout from "./routes/AppLayout.jsx";
import { OrganizationProvider } from "./contexts/OrganizationContext.jsx";
import "./index.css";

export const UserContext = React.createContext(null);

const App = () => {
  const [user, setUser] = useState(null);
  const [loading, setLoading] = useState(true);
  const location = useLocation();

  useEffect(() => {
    // Check authentication status only once on mount
    let mounted = true;
    const checkAuth = async () => {
      try {
        const u = await api.me();
        if (mounted) {
          setUser(u);
        }
      } catch (error) {
        // If authentication fails, clear user state
        if (mounted) {
          setUser(null);
        }
      } finally {
        if (mounted) {
          setLoading(false);
        }
      }
    };
    checkAuth();
    
    return () => {
      mounted = false;
    };
  }, []);

  if (loading) {
    return (
      <div className="loading-overlay">
        <div style={{ textAlign: "center" }}>
          <div
            className="spinner spinner-lg"
            style={{
              width: "3rem",
              height: "3rem",
              margin: "0 auto var(--spacing-lg)",
              borderWidth: "4px",
            }}
          />
          <p style={{ color: "var(--text-secondary)", fontSize: "1.125rem", fontWeight: 500 }}>
            Loading...
          </p>
          <div
            style={{
              marginTop: "var(--spacing-md)",
              width: "200px",
              height: "4px",
              background: "var(--gray-200)",
              borderRadius: "var(--radius-full)",
              overflow: "hidden",
            }}
          >
            <div
              className="progress-fill"
              style={{
                width: "60%",
                height: "100%",
                animation: "progress 1.5s ease-out infinite",
              }}
            />
          </div>
        </div>
      </div>
    );
  }

  // Only redirect if loading is complete
  if (!loading) {
    // If not authenticated and trying to access /app -> go to /login
    if (!user && location.pathname.startsWith("/app")) {
      return <Navigate to="/login" replace />;
    }

    // If authenticated and on /login -> go to chat
    if (user && location.pathname === "/login") {
      return <Navigate to="/app/chat" replace />;
    }
  }

  return (
    <UserContext.Provider value={{ user, setUser }}>
      <OrganizationProvider>
        <Routes>
          <Route path="/login" element={<LoginPage />} />
          <Route path="/app/*" element={<AppLayout />} />
          <Route
            path="*"
            element={<Navigate to={user ? "/app/chat" : "/login"} replace />}
          />
        </Routes>
      </OrganizationProvider>
    </UserContext.Provider>
  );
};

export default App;
