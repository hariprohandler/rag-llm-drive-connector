import React, { useState } from "react";
import { api } from "../api.js";

const DocumentsPage = () => {
  const [activeTab, setActiveTab] = useState("local"); // 'local', 'googledrive', 'onedrive'
  const [status, setStatus] = useState(null);
  const [loading, setLoading] = useState(false);
  const [dragActive, setDragActive] = useState(false);
  const [uploadProgress, setUploadProgress] = useState(0);
  
  // Google Drive state
  const [googleFolderId, setGoogleFolderId] = useState("");
  const [googleLoading, setGoogleLoading] = useState(false);
  
  // OneDrive state
  const [oneDrivePath, setOneDrivePath] = useState("");
  const [oneDriveLoading, setOneDriveLoading] = useState(false);

  const handleUpload = async (files) => {
    if (!files || files.length === 0) return;

    setLoading(true);
    setStatus(null);
    setUploadProgress(0);

    const formData = new FormData();
    Array.from(files).forEach((file) => formData.append("files", file));

    // Simulate progress (since we can't track actual upload progress easily)
    const progressInterval = setInterval(() => {
      setUploadProgress((prev) => {
        if (prev >= 90) {
          clearInterval(progressInterval);
          return 90;
        }
        return prev + 10;
      });
    }, 200);

    try {
      const res = await fetch(
        `${import.meta.env.VITE_BACKEND_BASE_URL || "http://localhost:8000"}/api/ingest/upload`,
        {
          method: "POST",
          credentials: "include",
          body: formData,
        }
      );

      clearInterval(progressInterval);
      setUploadProgress(100);

      if (!res.ok) {
        const errorText = await res.text();
        throw new Error(errorText || "Upload failed");
      }

      const data = await res.json();
      setStatus({
        type: "success",
        message: `Successfully uploaded and ingested ${files.length} file(s). Knowledge base ID: ${data.knowledge_base_id}`,
      });
      
      setTimeout(() => {
        setUploadProgress(0);
      }, 1000);
    } catch (e) {
      clearInterval(progressInterval);
      setUploadProgress(0);
      setStatus({
        type: "error",
        message: `Error: ${e.message}`,
      });
    } finally {
      setLoading(false);
    }
  };

  const handleGoogleDriveIngest = async () => {
    if (!googleFolderId.trim()) {
      setStatus({
        type: "error",
        message: "Please enter a Google Drive folder ID",
      });
      return;
    }

    setGoogleLoading(true);
    setStatus(null);

    try {
      const data = await api.ingestGoogleDrive({ folder_id: googleFolderId.trim() });
      setStatus({
        type: "success",
        message: `Successfully ingested Google Drive folder. Knowledge base ID: ${data.knowledge_base_id || "N/A"}`,
      });
      setGoogleFolderId("");
    } catch (e) {
      let errorMessage = "Failed to ingest from Google Drive";
      try {
        const errorData = JSON.parse(e.message);
        errorMessage = errorData.detail || errorMessage;
      } catch {
        errorMessage = e.message || errorMessage;
      }
      setStatus({
        type: "error",
        message: `Error: ${errorMessage}`,
      });
    } finally {
      setGoogleLoading(false);
    }
  };

  const handleOneDriveIngest = async () => {
    if (!oneDrivePath.trim()) {
      setStatus({
        type: "error",
        message: "Please enter a OneDrive folder path",
      });
      return;
    }

    setOneDriveLoading(true);
    setStatus(null);

    try {
      const data = await api.ingestOneDrive({ folder_path: oneDrivePath.trim() });
      setStatus({
        type: "success",
        message: `Successfully ingested OneDrive folder. Knowledge base ID: ${data.knowledge_base_id || "N/A"}`,
      });
      setOneDrivePath("");
    } catch (e) {
      let errorMessage = "Failed to ingest from OneDrive";
      try {
        const errorData = JSON.parse(e.message);
        errorMessage = errorData.detail || errorMessage;
      } catch {
        errorMessage = e.message || errorMessage;
      }
      setStatus({
        type: "error",
        message: `Error: ${errorMessage}`,
      });
    } finally {
      setOneDriveLoading(false);
    }
  };

  const handleFileInput = (e) => {
    handleUpload(e.target.files);
  };

  const handleDrag = (e) => {
    e.preventDefault();
    e.stopPropagation();
    if (e.type === "dragenter" || e.type === "dragover") {
      setDragActive(true);
    } else if (e.type === "dragleave") {
      setDragActive(false);
    }
  };

  const handleDrop = (e) => {
    e.preventDefault();
    e.stopPropagation();
    setDragActive(false);
    if (e.dataTransfer.files && e.dataTransfer.files.length > 0) {
      handleUpload(e.dataTransfer.files);
    }
  };

  const tabs = [
    { id: "local", label: "Local Files", icon: "📁" },
    { id: "googledrive", label: "Google Drive", icon: "☁️" },
    { id: "onedrive", label: "Microsoft OneDrive", icon: "📂" },
  ];

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
          Document Management
        </h1>
        <p style={{ color: "var(--text-secondary)", fontSize: "0.875rem" }}>
          Connect to Google Drive, OneDrive, or upload local files for RAG-based queries.
        </p>
      </div>

      {/* Tab Navigation */}
      <div
        className="card fade-in-up"
        style={{
          marginBottom: "var(--spacing-lg)",
          padding: "var(--spacing-sm)",
          display: "flex",
          gap: "var(--spacing-sm)",
          flexWrap: "wrap",
        }}
      >
        {tabs.map((tab) => (
          <button
            key={tab.id}
            onClick={() => setActiveTab(tab.id)}
            className={`btn ${activeTab === tab.id ? "btn-primary" : "btn-secondary"}`}
            style={{
              flex: "1 1 auto",
              minWidth: "120px",
              display: "flex",
              alignItems: "center",
              justifyContent: "center",
              gap: "var(--spacing-xs)",
              fontSize: "0.875rem",
              fontWeight: 500,
              transition: "all var(--transition-base)",
            }}
          >
            <span style={{ fontSize: "1.125rem" }}>{tab.icon}</span>
            <span>{tab.label}</span>
          </button>
        ))}
      </div>

      {/* Local Files Tab */}
      {activeTab === "local" && (
        <div className="card fade-in-up" style={{ marginBottom: "var(--spacing-lg)" }}>
          <div
            onDragEnter={handleDrag}
            onDragLeave={handleDrag}
            onDragOver={handleDrag}
            onDrop={handleDrop}
            className={`hover-lift ${dragActive ? "scale-in" : ""}`}
            style={{
              border: `2px dashed ${dragActive ? "var(--primary)" : "var(--gray-300)"}`,
              borderRadius: "var(--radius-lg)",
              padding: "var(--spacing-2xl)",
              textAlign: "center",
              background: dragActive ? "var(--gray-50)" : "transparent",
              transition: "all var(--transition-base)",
              cursor: "pointer",
              position: "relative",
              overflow: "hidden",
            }}
          >
            {loading && (
              <div
                style={{
                  position: "absolute",
                  top: 0,
                  left: 0,
                  right: 0,
                  height: "4px",
                  background: "var(--gray-200)",
                }}
              >
                <div
                  className="progress-fill"
                  style={{
                    width: `${uploadProgress}%`,
                    height: "100%",
                  }}
                />
              </div>
            )}
            <div
              className={dragActive ? "bounce" : ""}
              style={{
                fontSize: "3rem",
                marginBottom: "var(--spacing-md)",
                transition: "transform var(--transition-base)",
              }}
            >
              📄
            </div>
            <h3 style={{ marginBottom: "var(--spacing-sm)", fontSize: "1.125rem", fontWeight: 600 }}>
              {loading ? "Uploading..." : dragActive ? "Drop files here" : "Drop files here or click to upload"}
            </h3>
            <p style={{ color: "var(--text-secondary)", marginBottom: "var(--spacing-lg)", fontSize: "0.875rem" }}>
              Supported formats: PDF, DOCX, TXT, MD, CSV
            </p>
            <label>
              <input
                type="file"
                multiple
                onChange={handleFileInput}
                disabled={loading}
                style={{ display: "none" }}
                accept=".pdf,.docx,.txt,.md,.csv"
              />
              <span className="btn btn-primary" style={{ pointerEvents: loading ? "none" : "auto" }}>
                {loading ? (
                  <>
                    <div className="spinner" style={{ width: "1rem", height: "1rem" }} />
                    Uploading...
                  </>
                ) : (
                  "Choose Files"
                )}
              </span>
            </label>
          </div>
        </div>
      )}

      {/* Google Drive Tab */}
      {activeTab === "googledrive" && (
        <div className="card fade-in-up" style={{ marginBottom: "var(--spacing-lg)" }}>
          <div style={{ textAlign: "center", marginBottom: "var(--spacing-xl)" }}>
            <div
              style={{
                fontSize: "3rem",
                marginBottom: "var(--spacing-md)",
              }}
            >
              ☁️
            </div>
            <h3 style={{ marginBottom: "var(--spacing-sm)", fontSize: "1.25rem", fontWeight: 600 }}>
              Connect Google Drive
            </h3>
            <p style={{ color: "var(--text-secondary)", fontSize: "0.875rem", marginBottom: "var(--spacing-lg)" }}>
              Enter the Google Drive folder ID to ingest documents
            </p>
          </div>

          <div style={{ marginBottom: "var(--spacing-lg)" }}>
            <label
              style={{
                display: "block",
                marginBottom: "var(--spacing-sm)",
                fontWeight: 500,
                fontSize: "0.875rem",
                color: "var(--text-primary)",
              }}
            >
              Folder ID
            </label>
            <input
              type="text"
              value={googleFolderId}
              onChange={(e) => setGoogleFolderId(e.target.value)}
              placeholder="e.g., 1BxiMVs0XRA5nFMdKvBdBZjgmUUqptlbs74OgvE2upms"
              disabled={googleLoading}
              className="input"
              style={{
                width: "100%",
                padding: "var(--spacing-md)",
                fontSize: "0.875rem",
              }}
            />
            <p
              style={{
                marginTop: "var(--spacing-xs)",
                fontSize: "0.75rem",
                color: "var(--text-secondary)",
              }}
            >
              You can find the folder ID in the Google Drive URL:{" "}
              <code style={{ background: "var(--gray-100)", padding: "2px 4px", borderRadius: "4px" }}>
                drive.google.com/drive/folders/[FOLDER_ID]
              </code>
            </p>
          </div>

          <button
            onClick={handleGoogleDriveIngest}
            disabled={googleLoading || !googleFolderId.trim()}
            className="btn btn-primary"
            style={{
              width: "100%",
              display: "flex",
              alignItems: "center",
              justifyContent: "center",
              gap: "var(--spacing-sm)",
            }}
          >
            {googleLoading ? (
              <>
                <div className="spinner" style={{ width: "1rem", height: "1rem" }} />
                Connecting...
              </>
            ) : (
              <>
                <span>🔗</span>
                Connect & Ingest
              </>
            )}
          </button>
        </div>
      )}

      {/* OneDrive Tab */}
      {activeTab === "onedrive" && (
        <div className="card fade-in-up" style={{ marginBottom: "var(--spacing-lg)" }}>
          <div style={{ textAlign: "center", marginBottom: "var(--spacing-xl)" }}>
            <div
              style={{
                fontSize: "3rem",
                marginBottom: "var(--spacing-md)",
              }}
            >
              📂
            </div>
            <h3 style={{ marginBottom: "var(--spacing-sm)", fontSize: "1.25rem", fontWeight: 600 }}>
              Connect Microsoft OneDrive
            </h3>
            <p style={{ color: "var(--text-secondary)", fontSize: "0.875rem", marginBottom: "var(--spacing-lg)" }}>
              Enter the OneDrive folder path to ingest documents
            </p>
          </div>

          <div style={{ marginBottom: "var(--spacing-lg)" }}>
            <label
              style={{
                display: "block",
                marginBottom: "var(--spacing-sm)",
                fontWeight: 500,
                fontSize: "0.875rem",
                color: "var(--text-primary)",
              }}
            >
              Folder Path
            </label>
            <input
              type="text"
              value={oneDrivePath}
              onChange={(e) => setOneDrivePath(e.target.value)}
              placeholder="e.g., /Documents/MyFolder or /drive/root:/Documents"
              disabled={oneDriveLoading}
              className="input"
              style={{
                width: "100%",
                padding: "var(--spacing-md)",
                fontSize: "0.875rem",
              }}
            />
            <p
              style={{
                marginTop: "var(--spacing-xs)",
                fontSize: "0.75rem",
                color: "var(--text-secondary)",
              }}
            >
              Enter the path to the folder you want to ingest from OneDrive
            </p>
          </div>

          <button
            onClick={handleOneDriveIngest}
            disabled={oneDriveLoading || !oneDrivePath.trim()}
            className="btn btn-primary"
            style={{
              width: "100%",
              display: "flex",
              alignItems: "center",
              justifyContent: "center",
              gap: "var(--spacing-sm)",
            }}
          >
            {oneDriveLoading ? (
              <>
                <div className="spinner" style={{ width: "1rem", height: "1rem" }} />
                Connecting...
              </>
            ) : (
              <>
                <span>🔗</span>
                Connect & Ingest
              </>
            )}
          </button>
        </div>
      )}

      {/* Status Message */}
      {status && (
        <div
          className={`fade-in-down ${status.type === "success" ? "scale-in" : ""}`}
          style={{
            padding: "var(--spacing-md)",
            background: status.type === "success" ? "#d1fae5" : "#fee2e2",
            color: status.type === "success" ? "#065f46" : "#991b1b",
            border: `1px solid ${status.type === "success" ? "#10b981" : "#ef4444"}`,
            borderRadius: "var(--radius-md)",
            display: "flex",
            alignItems: "center",
            gap: "var(--spacing-sm)",
          }}
        >
          <span style={{ fontSize: "1.25rem" }}>{status.type === "success" ? "✓" : "✕"}</span>
          <span>{status.message}</span>
        </div>
      )}
    </div>
  );
};

export default DocumentsPage;
