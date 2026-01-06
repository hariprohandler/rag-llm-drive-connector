import React, { useState, useEffect } from "react";
import { api } from "../api.js";

const DocumentsPage = () => {
  const [activeTab, setActiveTab] = useState("local");
  const [status, setStatus] = useState(null);
  const [loading, setLoading] = useState(false);
  const [dragActive, setDragActive] = useState(false);
  const [uploadProgress, setUploadProgress] = useState(0);
  
  // Drive connection status
  const [googleConnected, setGoogleConnected] = useState(false);
  const [microsoftConnected, setMicrosoftConnected] = useState(false);
  const [checkingStatus, setCheckingStatus] = useState(true);
  
  // File browser state
  const [googleFiles, setGoogleFiles] = useState([]);
  const [microsoftFiles, setMicrosoftFiles] = useState([]);
  const [selectedItems, setSelectedItems] = useState([]);
  const [currentFolder, setCurrentFolder] = useState({ google: null, microsoft: "/" });
  const [loadingFiles, setLoadingFiles] = useState(false);
  
  // Ingestion task state
  const [activeTask, setActiveTask] = useState(null);
  const [taskProgress, setTaskProgress] = useState(null);

  // Check connection status on mount and tab change
  useEffect(() => {
    checkConnectionStatus();
  }, [activeTab]);

  // Poll task progress if active
  useEffect(() => {
    if (activeTask) {
      const interval = setInterval(async () => {
        try {
          const task = await api.getIngestionTaskStatus(activeTask);
          setTaskProgress(task);
          if (task.status === "completed" || task.status === "failed") {
            clearInterval(interval);
            setActiveTask(null);
            if (task.status === "completed") {
              setStatus({
                type: "success",
                message: `Ingestion completed! Knowledge base ID: ${task.knowledge_base_id || "N/A"}`,
              });
            }
          }
        } catch (e) {
          console.error("Error fetching task status:", e);
        }
      }, 2000);
      return () => clearInterval(interval);
    }
  }, [activeTask]);

  const checkConnectionStatus = async () => {
    setCheckingStatus(true);
    try {
      if (activeTab === "googledrive") {
        const status = await api.checkGoogleDriveStatus();
        setGoogleConnected(status.connected);
        if (status.connected) {
          loadGoogleFiles();
        }
      } else if (activeTab === "onedrive") {
        const status = await api.checkMicrosoftOneDriveStatus();
        setMicrosoftConnected(status.connected);
        if (status.connected) {
          loadMicrosoftFiles();
        }
      }
    } catch (e) {
      console.error("Error checking connection status:", e);
    } finally {
      setCheckingStatus(false);
    }
  };

  const loadGoogleFiles = async (folderId = null) => {
    setLoadingFiles(true);
    try {
      const result = await api.listGoogleFiles(folderId);
      setGoogleFiles(result.files || []);
      setCurrentFolder({ ...currentFolder, google: folderId });
    } catch (e) {
      setStatus({
        type: "error",
        message: `Error loading files: ${e.message}`,
      });
    } finally {
      setLoadingFiles(false);
    }
  };

  const loadMicrosoftFiles = async (folderPath = "/") => {
    setLoadingFiles(true);
    try {
      const result = await api.listMicrosoftFiles(folderPath);
      setMicrosoftFiles(result.files || []);
      setCurrentFolder({ ...currentFolder, microsoft: folderPath });
    } catch (e) {
      setStatus({
        type: "error",
        message: `Error loading files: ${e.message}`,
      });
    } finally {
      setLoadingFiles(false);
    }
  };

  const toggleItemSelection = (item) => {
    setSelectedItems((prev) => {
      const exists = prev.find((i) => i.id === item.id);
      if (exists) {
        return prev.filter((i) => i.id !== item.id);
      } else {
        return [...prev, item];
      }
    });
  };

  const handleStartIngestion = async (provider) => {
    if (selectedItems.length === 0) {
      setStatus({
        type: "error",
        message: "Please select at least one file or folder",
      });
      return;
    }

    try {
      const items = selectedItems.map((item) => ({
        id: item.id,
        name: item.name,
        type: item.type,
        path: item.path,
      }));

      let result;
      if (provider === "google") {
        result = await api.startGoogleIngestion({ items });
      } else {
        result = await api.startMicrosoftIngestion({ items });
      }

      setActiveTask(result.task_id);
      setSelectedItems([]);
      setStatus({
        type: "info",
        message: "Ingestion started in background. Progress will be shown below.",
      });
    } catch (e) {
      setStatus({
        type: "error",
        message: `Error starting ingestion: ${e.message}`,
      });
    }
  };

  const handleUpload = async (files) => {
    if (!files || files.length === 0) return;

    setLoading(true);
    setStatus(null);
    setUploadProgress(0);

    const formData = new FormData();
    Array.from(files).forEach((file) => formData.append("files", file));

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

  const tabs = [
    { id: "local", label: "Local Files", icon: "📁" },
    { id: "googledrive", label: "Google Drive", icon: "☁️" },
    { id: "onedrive", label: "Microsoft OneDrive", icon: "📂" },
  ];

  const currentFiles = activeTab === "googledrive" ? googleFiles : microsoftFiles;

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
            onClick={() => {
              setActiveTab(tab.id);
              setSelectedItems([]);
            }}
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
        <div className="fade-in-up">
          {checkingStatus ? (
            <div className="card" style={{ textAlign: "center", padding: "var(--spacing-2xl)" }}>
              <div className="spinner" style={{ width: "2rem", height: "2rem", margin: "0 auto" }} />
              <p style={{ marginTop: "var(--spacing-md)", color: "var(--text-secondary)" }}>Checking connection...</p>
            </div>
          ) : !googleConnected ? (
            <div className="card fade-in-up" style={{ marginBottom: "var(--spacing-lg)", textAlign: "center", padding: "var(--spacing-2xl)" }}>
              <div style={{ fontSize: "3rem", marginBottom: "var(--spacing-md)" }}>☁️</div>
              <h3 style={{ marginBottom: "var(--spacing-sm)", fontSize: "1.25rem", fontWeight: 600 }}>
                Connect Google Drive
              </h3>
              <p style={{ color: "var(--text-secondary)", marginBottom: "var(--spacing-lg)", fontSize: "0.875rem" }}>
                Connect your Google Drive to browse and select files for RAG ingestion
              </p>
              <button
                onClick={() => api.connectGoogleDrive()}
                className="btn btn-primary"
                style={{
                  display: "flex",
                  alignItems: "center",
                  gap: "var(--spacing-sm)",
                  margin: "0 auto",
                }}
              >
                <span>🔗</span>
                Connect Google Drive
              </button>
            </div>
          ) : (
            <>
              {/* File Browser */}
              <div className="card fade-in-up" style={{ marginBottom: "var(--spacing-lg)" }}>
                <div style={{ display: "flex", justifyContent: "space-between", alignItems: "center", marginBottom: "var(--spacing-md)" }}>
                  <h3 style={{ fontSize: "1.125rem", fontWeight: 600 }}>Google Drive Files</h3>
                  <div style={{ display: "flex", gap: "var(--spacing-sm)" }}>
                    {currentFolder.google && (
                      <button
                        onClick={() => loadGoogleFiles(null)}
                        className="btn btn-secondary"
                        style={{ fontSize: "0.875rem" }}
                      >
                        ← Root
                      </button>
                    )}
                    <button
                      onClick={() => loadGoogleFiles(currentFolder.google)}
                      className="btn btn-secondary"
                      style={{ fontSize: "0.875rem" }}
                      disabled={loadingFiles}
                    >
                      {loadingFiles ? "Loading..." : "🔄 Refresh"}
                    </button>
                  </div>
                </div>
                
                {loadingFiles ? (
                  <div style={{ textAlign: "center", padding: "var(--spacing-xl)" }}>
                    <div className="spinner" style={{ width: "2rem", height: "2rem", margin: "0 auto" }} />
                  </div>
                ) : (
                  <div style={{ maxHeight: "400px", overflowY: "auto" }}>
                    {currentFiles.length === 0 ? (
                      <p style={{ textAlign: "center", color: "var(--text-secondary)", padding: "var(--spacing-xl)" }}>
                        No files found
                      </p>
                    ) : (
                      <div style={{ display: "flex", flexDirection: "column", gap: "var(--spacing-xs)" }}>
                        {currentFiles.map((file) => {
                          const isSelected = selectedItems.find((i) => i.id === file.id);
                          return (
                            <div
                              key={file.id}
                              onClick={() => {
                                if (file.type === "folder") {
                                  loadGoogleFiles(file.id);
                                } else {
                                  toggleItemSelection(file);
                                }
                              }}
                              className={`hover-lift ${isSelected ? "scale-in" : ""}`}
                              style={{
                                padding: "var(--spacing-md)",
                                border: `1px solid ${isSelected ? "var(--primary)" : "var(--gray-300)"}`,
                                borderRadius: "var(--radius-md)",
                                cursor: "pointer",
                                background: isSelected ? "var(--primary-light)" : "transparent",
                                display: "flex",
                                alignItems: "center",
                                gap: "var(--spacing-sm)",
                              }}
                            >
                              <span style={{ fontSize: "1.25rem" }}>{file.type === "folder" ? "📁" : "📄"}</span>
                              <div style={{ flex: 1 }}>
                                <div style={{ fontWeight: 500 }}>{file.name}</div>
                                <div style={{ fontSize: "0.75rem", color: "var(--text-secondary)" }}>
                                  {file.type === "folder" ? "Folder" : `${(parseInt(file.size) / 1024).toFixed(2)} KB`}
                                </div>
                              </div>
                              {isSelected && <span style={{ color: "var(--primary)" }}>✓</span>}
                            </div>
                          );
                        })}
                      </div>
                    )}
                  </div>
                )}
              </div>

              {/* Selection and Actions */}
              {selectedItems.length > 0 && (
                <div className="card fade-in-up" style={{ marginBottom: "var(--spacing-lg)" }}>
                  <div style={{ marginBottom: "var(--spacing-md)" }}>
                    <strong>{selectedItems.length}</strong> item(s) selected
                  </div>
                  <button
                    onClick={() => handleStartIngestion("google")}
                    className="btn btn-primary"
                    style={{ width: "100%" }}
                  >
                    Start Ingestion
                  </button>
                </div>
              )}
            </>
          )}
        </div>
      )}

      {/* OneDrive Tab */}
      {activeTab === "onedrive" && (
        <div className="fade-in-up">
          {checkingStatus ? (
            <div className="card" style={{ textAlign: "center", padding: "var(--spacing-2xl)" }}>
              <div className="spinner" style={{ width: "2rem", height: "2rem", margin: "0 auto" }} />
              <p style={{ marginTop: "var(--spacing-md)", color: "var(--text-secondary)" }}>Checking connection...</p>
            </div>
          ) : !microsoftConnected ? (
            <div className="card fade-in-up" style={{ marginBottom: "var(--spacing-lg)", textAlign: "center", padding: "var(--spacing-2xl)" }}>
              <div style={{ fontSize: "3rem", marginBottom: "var(--spacing-md)" }}>📂</div>
              <h3 style={{ marginBottom: "var(--spacing-sm)", fontSize: "1.25rem", fontWeight: 600 }}>
                Connect Microsoft OneDrive
              </h3>
              <p style={{ color: "var(--text-secondary)", marginBottom: "var(--spacing-lg)", fontSize: "0.875rem" }}>
                Connect your OneDrive to browse and select files for RAG ingestion
              </p>
              <button
                onClick={() => api.connectMicrosoftOneDrive()}
                className="btn btn-primary"
                style={{
                  display: "flex",
                  alignItems: "center",
                  gap: "var(--spacing-sm)",
                  margin: "0 auto",
                }}
              >
                <span>🔗</span>
                Connect OneDrive
              </button>
            </div>
          ) : (
            <>
              {/* File Browser - Similar to Google Drive */}
              <div className="card fade-in-up" style={{ marginBottom: "var(--spacing-lg)" }}>
                <div style={{ display: "flex", justifyContent: "space-between", alignItems: "center", marginBottom: "var(--spacing-md)" }}>
                  <h3 style={{ fontSize: "1.125rem", fontWeight: 600 }}>OneDrive Files</h3>
                  <div style={{ display: "flex", gap: "var(--spacing-sm)" }}>
                    {currentFolder.microsoft !== "/" && (
                      <button
                        onClick={() => loadMicrosoftFiles("/")}
                        className="btn btn-secondary"
                        style={{ fontSize: "0.875rem" }}
                      >
                        ← Root
                      </button>
                    )}
                    <button
                      onClick={() => loadMicrosoftFiles(currentFolder.microsoft)}
                      className="btn btn-secondary"
                      style={{ fontSize: "0.875rem" }}
                      disabled={loadingFiles}
                    >
                      {loadingFiles ? "Loading..." : "🔄 Refresh"}
                    </button>
                  </div>
                </div>
                
                {loadingFiles ? (
                  <div style={{ textAlign: "center", padding: "var(--spacing-xl)" }}>
                    <div className="spinner" style={{ width: "2rem", height: "2rem", margin: "0 auto" }} />
                  </div>
                ) : (
                  <div style={{ maxHeight: "400px", overflowY: "auto" }}>
                    {currentFiles.length === 0 ? (
                      <p style={{ textAlign: "center", color: "var(--text-secondary)", padding: "var(--spacing-xl)" }}>
                        No files found
                      </p>
                    ) : (
                      <div style={{ display: "flex", flexDirection: "column", gap: "var(--spacing-xs)" }}>
                        {currentFiles.map((file) => {
                          const isSelected = selectedItems.find((i) => i.id === file.id);
                          return (
                            <div
                              key={file.id}
                              onClick={() => {
                                if (file.type === "folder") {
                                  loadMicrosoftFiles(file.path || file.id);
                                } else {
                                  toggleItemSelection(file);
                                }
                              }}
                              className={`hover-lift ${isSelected ? "scale-in" : ""}`}
                              style={{
                                padding: "var(--spacing-md)",
                                border: `1px solid ${isSelected ? "var(--primary)" : "var(--gray-300)"}`,
                                borderRadius: "var(--radius-md)",
                                cursor: "pointer",
                                background: isSelected ? "var(--primary-light)" : "transparent",
                                display: "flex",
                                alignItems: "center",
                                gap: "var(--spacing-sm)",
                              }}
                            >
                              <span style={{ fontSize: "1.25rem" }}>{file.type === "folder" ? "📁" : "📄"}</span>
                              <div style={{ flex: 1 }}>
                                <div style={{ fontWeight: 500 }}>{file.name}</div>
                                <div style={{ fontSize: "0.75rem", color: "var(--text-secondary)" }}>
                                  {file.type === "folder" ? "Folder" : `${(parseInt(file.size) / 1024).toFixed(2)} KB`}
                                </div>
                              </div>
                              {isSelected && <span style={{ color: "var(--primary)" }}>✓</span>}
                            </div>
                          );
                        })}
                      </div>
                    )}
                  </div>
                )}
              </div>

              {/* Selection and Actions */}
              {selectedItems.length > 0 && (
                <div className="card fade-in-up" style={{ marginBottom: "var(--spacing-lg)" }}>
                  <div style={{ marginBottom: "var(--spacing-md)" }}>
                    <strong>{selectedItems.length}</strong> item(s) selected
                  </div>
                  <button
                    onClick={() => handleStartIngestion("microsoft")}
                    className="btn btn-primary"
                    style={{ width: "100%" }}
                  >
                    Start Ingestion
                  </button>
                </div>
              )}
            </>
          )}
        </div>
      )}

      {/* Task Progress */}
      {taskProgress && (
        <div className="card fade-in-up" style={{ marginBottom: "var(--spacing-lg)" }}>
          <h3 style={{ marginBottom: "var(--spacing-md)", fontSize: "1.125rem", fontWeight: 600 }}>
            Ingestion Progress
          </h3>
          <div style={{ marginBottom: "var(--spacing-sm)" }}>
            <div style={{ display: "flex", justifyContent: "space-between", marginBottom: "var(--spacing-xs)" }}>
              <span>{taskProgress.message || "Processing..."}</span>
              <span>{taskProgress.progress.toFixed(1)}%</span>
            </div>
            <div
              style={{
                width: "100%",
                height: "8px",
                background: "var(--gray-200)",
                borderRadius: "var(--radius-full)",
                overflow: "hidden",
              }}
            >
              <div
                style={{
                  width: `${taskProgress.progress}%`,
                  height: "100%",
                  background: "var(--primary)",
                  transition: "width 0.3s ease",
                }}
              />
            </div>
          </div>
          <div style={{ fontSize: "0.875rem", color: "var(--text-secondary)" }}>
            {taskProgress.processed_items} of {taskProgress.total_items} items processed
          </div>
        </div>
      )}

      {/* Status Message */}
      {status && (
        <div
          className={`fade-in-down ${status.type === "success" ? "scale-in" : ""}`}
          style={{
            padding: "var(--spacing-md)",
            background: status.type === "success" ? "#d1fae5" : status.type === "info" ? "#dbeafe" : "#fee2e2",
            color: status.type === "success" ? "#065f46" : status.type === "info" ? "#1e40af" : "#991b1b",
            border: `1px solid ${status.type === "success" ? "#10b981" : status.type === "info" ? "#3b82f6" : "#ef4444"}`,
            borderRadius: "var(--radius-md)",
            display: "flex",
            alignItems: "center",
            gap: "var(--spacing-sm)",
          }}
        >
          <span style={{ fontSize: "1.25rem" }}>
            {status.type === "success" ? "✓" : status.type === "info" ? "ℹ" : "✕"}
          </span>
          <span>{status.message}</span>
        </div>
      )}
    </div>
  );
};

export default DocumentsPage;
