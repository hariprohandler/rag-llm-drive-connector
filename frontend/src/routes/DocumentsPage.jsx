import React, { useState } from "react";
import { api } from "../api.js";

const DocumentsPage = () => {
  const [status, setStatus] = useState(null);
  const [loading, setLoading] = useState(false);
  const [dragActive, setDragActive] = useState(false);
  const [uploadProgress, setUploadProgress] = useState(0);

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
          Upload and manage documents for RAG-based queries. Supported formats: PDF, DOCX, TXT, MD.
        </p>
      </div>

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
            Select multiple files to upload
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
