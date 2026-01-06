import React, { useState, useEffect, useContext } from "react";
import { api } from "../api.js";
import { UserContext } from "../App.jsx";
import { useOrganization } from "../contexts/OrganizationContext.jsx";

const GeneralSettingsPage = () => {
  const { user } = useContext(UserContext);
  const { organizationName, setOrganizationName } = useOrganization();
  const [orgNameInput, setOrgNameInput] = useState(organizationName);
  const [saving, setSaving] = useState(false);
  const [saved, setSaved] = useState(false);

  useEffect(() => {
    setOrgNameInput(organizationName);
  }, [organizationName]);

  const handleSaveOrganizationName = async () => {
    if (!orgNameInput.trim()) {
      alert("Organization name cannot be empty");
      return;
    }
    setSaving(true);
    setSaved(false);
    try {
      await setOrganizationName(orgNameInput.trim());
      setSaved(true);
      setTimeout(() => setSaved(false), 3000);
    } catch (e) {
      alert(`Error: ${e.message}`);
    } finally {
      setSaving(false);
    }
  };

  const formatDate = (dateString) => {
    if (!dateString) return "N/A";
    try {
      return new Date(dateString).toLocaleDateString("en-US", {
        year: "numeric",
        month: "long",
        day: "numeric",
        hour: "2-digit",
        minute: "2-digit",
      });
    } catch {
      return dateString;
    }
  };

  return (
    <div className="page-enter">
      <div className="fade-in-down" style={{ marginBottom: "var(--spacing-xl)" }}>
        <h1
          style={{
            fontSize: "2rem",
            fontWeight: 700,
            marginBottom: "var(--spacing-sm)",
            color: "var(--text-primary)",
          }}
        >
          General Settings
        </h1>
        <p style={{ color: "var(--text-secondary)", fontSize: "0.875rem" }}>
          Manage your profile information and organization settings.
        </p>
      </div>

      {/* Profile Information */}
      <div className="card fade-in-up" style={{ marginBottom: "var(--spacing-xl)" }}>
        <h2
          style={{
            fontSize: "1.25rem",
            fontWeight: 600,
            marginBottom: "var(--spacing-lg)",
            color: "var(--text-primary)",
          }}
        >
          Profile Information
        </h2>
        <div style={{ display: "flex", flexDirection: "column", gap: "var(--spacing-md)" }}>
          {user?.picture && (
            <div style={{ marginBottom: "var(--spacing-md)" }}>
              <img
                src={user.picture}
                alt="Profile"
                style={{
                  width: "80px",
                  height: "80px",
                  borderRadius: "50%",
                  objectFit: "cover",
                  border: "2px solid var(--gray-200)",
                }}
              />
            </div>
          )}
          <div>
            <label
              style={{
                display: "block",
                marginBottom: "var(--spacing-xs)",
                fontSize: "0.875rem",
                fontWeight: 500,
                color: "var(--text-primary)",
              }}
            >
              Name
            </label>
            <input
              type="text"
              value={user?.name || ""}
              disabled
              className="input"
              style={{ background: "var(--gray-50)", cursor: "not-allowed" }}
            />
            <p style={{ fontSize: "0.75rem", color: "var(--text-secondary)", marginTop: "var(--spacing-xs)" }}>
              Name is managed by your authentication provider
            </p>
          </div>
          <div>
            <label
              style={{
                display: "block",
                marginBottom: "var(--spacing-xs)",
                fontSize: "0.875rem",
                fontWeight: 500,
                color: "var(--text-primary)",
              }}
            >
              Email
            </label>
            <input
              type="email"
              value={user?.email || ""}
              disabled
              className="input"
              style={{ background: "var(--gray-50)", cursor: "not-allowed" }}
            />
          </div>
          <div>
            <label
              style={{
                display: "block",
                marginBottom: "var(--spacing-xs)",
                fontSize: "0.875rem",
                fontWeight: 500,
                color: "var(--text-primary)",
              }}
            >
              Authentication Provider
            </label>
            <input
              type="text"
              value={user?.provider ? user.provider.charAt(0).toUpperCase() + user.provider.slice(1) : ""}
              disabled
              className="input"
              style={{ background: "var(--gray-50)", cursor: "not-allowed" }}
            />
          </div>
          <div>
            <label
              style={{
                display: "block",
                marginBottom: "var(--spacing-xs)",
                fontSize: "0.875rem",
                fontWeight: 500,
                color: "var(--text-primary)",
              }}
            >
              Account Created
            </label>
            <input
              type="text"
              value={formatDate(user?.created_at)}
              disabled
              className="input"
              style={{ background: "var(--gray-50)", cursor: "not-allowed" }}
            />
          </div>
        </div>
      </div>

      {/* Organization Settings */}
      <div className="card fade-in-up">
        <h2
          style={{
            fontSize: "1.25rem",
            fontWeight: 600,
            marginBottom: "var(--spacing-lg)",
            color: "var(--text-primary)",
          }}
        >
          Organization Settings
        </h2>
        <div style={{ display: "flex", flexDirection: "column", gap: "var(--spacing-md)" }}>
          <div>
            <label
              style={{
                display: "block",
                marginBottom: "var(--spacing-xs)",
                fontSize: "0.875rem",
                fontWeight: 500,
                color: "var(--text-primary)",
              }}
            >
              Organization Name
            </label>
            <p
              style={{
                fontSize: "0.75rem",
                color: "var(--text-secondary)",
                marginBottom: "var(--spacing-sm)",
              }}
            >
              This name will be displayed throughout the application (e.g., "{orgNameInput} Assistant")
            </p>
            <input
              type="text"
              value={orgNameInput}
              onChange={(e) => setOrgNameInput(e.target.value)}
              className="input"
              placeholder="Enter organization name"
              maxLength={50}
            />
          </div>
          <div style={{ display: "flex", gap: "var(--spacing-md)", alignItems: "center" }}>
            <button
              onClick={handleSaveOrganizationName}
              disabled={saving || orgNameInput.trim() === organizationName}
              className="btn btn-primary hover-lift"
            >
              {saving ? (
                <>
                  <div className="spinner" style={{ width: "1rem", height: "1rem" }} />
                  Saving...
                </>
              ) : (
                "Save Organization Name"
              )}
            </button>
            {saved && (
              <span
                style={{
                  color: "var(--success)",
                  fontSize: "0.875rem",
                  display: "flex",
                  alignItems: "center",
                  gap: "var(--spacing-xs)",
                }}
                className="fade-in"
              >
                ✓ Saved successfully
              </span>
            )}
          </div>
        </div>
      </div>
    </div>
  );
};

export default GeneralSettingsPage;

