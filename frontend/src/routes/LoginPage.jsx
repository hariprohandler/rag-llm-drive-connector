import React from "react";
import { BACKEND_BASE_URL } from "../api.js";

const LoginPage = () => {
  const handleGoogle = () => {
    window.location.href = `${BACKEND_BASE_URL}/auth/login/google`;
  };

  const handleMicrosoft = () => {
    window.location.href = `${BACKEND_BASE_URL}/auth/login/microsoft`;
  };

  return (
    <div
      style={{
        minHeight: "100vh",
        display: "flex",
        justifyContent: "center",
        alignItems: "center",
        background:
          "linear-gradient(135deg, #e3f2fd 0%, #bbdefb 100%)"
      }}
    >
      <div
        style={{
          padding: 40,
          borderRadius: 16,
          boxShadow: "0 8px 24px rgba(0,0,0,0.12)",
          background: "#fff",
          maxWidth: 420,
          width: "100%",
          textAlign: "center"
        }}
      >
        <div
          style={{
            width: 80,
            height: 80,
            margin: "0 auto 24px",
            borderRadius: "50%",
            background:
              "linear-gradient(135deg, #667eea 0%, #764ba2 100%)",
            display: "flex",
            alignItems: "center",
            justifyContent: "center",
            fontSize: 40
          }}
        >
          🧠
        </div>
        <h1>RAG Chat Platform</h1>
        <p>Sign in to access your intelligent document assistant</p>
        <button
          onClick={handleGoogle}
          style={{
            width: "100%",
            marginTop: 16,
            padding: "10px 16px"
          }}
        >
          Continue with Google
        </button>
        <button
          onClick={handleMicrosoft}
          style={{
            width: "100%",
            marginTop: 8,
            padding: "10px 16px"
          }}
        >
          Continue with Microsoft
        </button>
      </div>
    </div>
  );
};

export default LoginPage;


