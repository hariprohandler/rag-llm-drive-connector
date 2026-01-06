import React, { useEffect, useState } from "react";
import { Routes, Route, Navigate, useLocation } from "react-router-dom";
import { api } from "./api.js";
import LoginPage from "./routes/LoginPage.jsx";
import AppLayout from "./routes/AppLayout.jsx";

export const UserContext = React.createContext(null);

const App = () => {
  const [user, setUser] = useState(null);
  const [loading, setLoading] = useState(true);
  const location = useLocation();

  useEffect(() => {
    api
      .me()
      .then((u) => setUser(u))
      .catch(() => setUser(null))
      .finally(() => setLoading(false));
  }, []);

  if (loading) {
    return <div>Loading...</div>;
  }

  // If not authenticated and trying to access /app -> go to /login
  if (!user && location.pathname.startsWith("/app")) {
    return <Navigate to="/login" replace />;
  }

  // If authenticated and on /login -> go to chat
  if (user && location.pathname === "/login") {
    return <Navigate to="/app/chat" replace />;
  }

  return (
    <UserContext.Provider value={{ user, setUser }}>
      <Routes>
        <Route path="/login" element={<LoginPage />} />
        <Route path="/app/*" element={<AppLayout />} />
        <Route
          path="*"
          element={<Navigate to={user ? "/app/chat" : "/login"} replace />}
        />
      </Routes>
    </UserContext.Provider>
  );
};

export default App;


