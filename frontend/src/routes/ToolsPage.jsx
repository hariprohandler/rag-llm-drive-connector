import React, { useEffect, useState } from "react";
import { api } from "../api.js";

const SkeletonLoader = () => (
  <div className="card">
    <div className="skeleton skeleton-title" />
    <div className="skeleton skeleton-text" />
    <div className="skeleton skeleton-text" style={{ width: "80%" }} />
  </div>
);

const ToolsPage = () => {
  const [tools, setTools] = useState([]);
  const [loading, setLoading] = useState(true);
  const [editingTool, setEditingTool] = useState(null);
  const [syncTasks, setSyncTasks] = useState({}); // task_id -> task data
  const [syncingTools, setSyncingTools] = useState(new Set());
  const [databaseConnections, setDatabaseConnections] = useState([]);
  const [loadingDatabases, setLoadingDatabases] = useState(true);
  const [editingDatabase, setEditingDatabase] = useState(null);
  const [showDatabaseForm, setShowDatabaseForm] = useState(false);

  useEffect(() => {
    loadTools();
    loadDatabaseConnections();
  }, []);

  const loadTools = async () => {
    try {
      setLoading(true);
      const data = await api.listTools();
      setTools(data || []);
    } catch (e) {
      console.error("Failed to load tools:", e);
    } finally {
      setLoading(false);
    }
  };

  const loadDatabaseConnections = async () => {
    try {
      setLoadingDatabases(true);
      const data = await api.listDatabaseConnections();
      setDatabaseConnections(data || []);
    } catch (e) {
      console.error("Failed to load database connections:", e);
    } finally {
      setLoadingDatabases(false);
    }
  };

  const handleSaveConfig = async (toolName, configData) => {
    try {
      const existing = tools.find(t => t.tool_name === toolName)?.config;
      
      // If updating and api_token is empty (was masked), don't include it in the update
      const updateConfigData = { ...configData };
      if (existing && (!updateConfigData.api_token || updateConfigData.api_token.trim() === "")) {
        delete updateConfigData.api_token;
      }
      
      if (existing) {
        await api.updateToolConfig(toolName, {
          is_active: true,
          config_data: updateConfigData
        });
      } else {
        await api.createToolConfig({
          tool_name: toolName,
          is_active: true,
          config_data: configData
        });
      }
      
      await loadTools();
      setEditingTool(null);
    } catch (e) {
      alert(`Error: ${e.message}`);
    }
  };

  const handleDeleteConfig = async (toolName) => {
    if (!confirm("Are you sure you want to delete this configuration?")) {
      return;
    }
    try {
      await api.deleteToolConfig(toolName);
      await loadTools();
    } catch (e) {
      alert(`Error: ${e.message}`);
    }
  };

  const handleSync = async (toolName) => {
    try {
      setSyncingTools(prev => new Set(prev).add(toolName));
      const result = await api.syncTool({ tool_name: toolName });
      
      if (result.task_id) {
        // Poll for sync status
        pollSyncStatus(result.task_id, toolName);
      }
    } catch (e) {
      alert(`Error starting sync: ${e.message}`);
      setSyncingTools(prev => {
        const newSet = new Set(prev);
        newSet.delete(toolName);
        return newSet;
      });
    }
  };

  const pollSyncStatus = async (taskId, toolName) => {
    const maxAttempts = 300; // 5 minutes max
    let attempts = 0;
    
    const poll = async () => {
      try {
        const status = await api.getSyncStatus(taskId);
        setSyncTasks(prev => ({ ...prev, [taskId]: status }));
        
        if (status.status === "completed" || status.status === "failed") {
          setSyncingTools(prev => {
            const newSet = new Set(prev);
            newSet.delete(toolName);
            return newSet;
          });
          await loadTools(); // Refresh to get updated sync status
          return;
        }
        
        attempts++;
        if (attempts < maxAttempts) {
          setTimeout(poll, 1000); // Poll every second
        }
      } catch (e) {
        console.error("Error polling sync status:", e);
        setSyncingTools(prev => {
          const newSet = new Set(prev);
          newSet.delete(toolName);
          return newSet;
        });
      }
    };
    
    poll();
  };

  const ToolConfigForm = ({ tool }) => {
    const [subdomain, setSubdomain] = useState(tool.config?.config_data?.subdomain || "");
    const [email, setEmail] = useState(tool.config?.config_data?.email || "");
    const hasExistingToken = tool.config?.config_data?.api_token === "••••••••";
    const [apiToken, setApiToken] = useState(hasExistingToken ? "" : (tool.config?.config_data?.api_token || ""));

    const handleSubmit = (e) => {
      e.preventDefault();
      if (!subdomain || !email || (!apiToken && !hasExistingToken)) {
        alert("Please fill in all required fields");
        return;
      }
      handleSaveConfig(tool.tool_name, {
        subdomain: subdomain.trim(),
        email: email.trim(),
        api_token: apiToken
      });
    };

    return (
      <form onSubmit={handleSubmit} style={{ display: "flex", flexDirection: "column", gap: "var(--spacing-md)" }}>
        {tool.config_fields?.map((field) => (
          <div key={field.name}>
            <label
              style={{
                display: "block",
                marginBottom: "var(--spacing-xs)",
                fontSize: "0.875rem",
                fontWeight: 500,
                color: "var(--text-primary)",
              }}
            >
              {field.label} {field.required && <span style={{ color: "var(--error)" }}>*</span>}
            </label>
            {field.type === "password" ? (
              <div>
                <input
                  type="password"
                  value={field.name === "api_token" ? apiToken : ""}
                  onChange={(e) => setApiToken(e.target.value)}
                  className="input"
                  placeholder={
                    field.name === "api_token" && hasExistingToken
                      ? "Enter new token to update, or leave blank to keep existing"
                      : (field.help || `Enter ${field.label.toLowerCase()}`)
                  }
                  required={field.required && !hasExistingToken}
                />
                {field.name === "api_token" && hasExistingToken && (
                  <p style={{ fontSize: "0.75rem", color: "var(--text-secondary)", marginTop: "var(--spacing-xs)", fontStyle: "italic" }}>
                    ✓ Token is configured. Leave blank to keep existing token, or enter a new token to update.
                  </p>
                )}
              </div>
            ) : field.type === "email" ? (
              <input
                type="email"
                value={field.name === "email" ? email : ""}
                onChange={(e) => setEmail(e.target.value)}
                className="input"
                placeholder={field.help || `Enter ${field.label.toLowerCase()}`}
                required={field.required}
              />
            ) : (
              <input
                type="text"
                value={field.name === "subdomain" ? subdomain : ""}
                onChange={(e) => setSubdomain(e.target.value)}
                className="input"
                placeholder={field.help || `Enter ${field.label.toLowerCase()}`}
                required={field.required}
              />
            )}
            {field.help && (
              <p style={{ fontSize: "0.75rem", color: "var(--text-secondary)", marginTop: "var(--spacing-xs)" }}>
                {field.help}
              </p>
            )}
          </div>
        ))}
        <div style={{ display: "flex", gap: "var(--spacing-md)" }}>
          <button 
            type="submit" 
            className="btn btn-primary"
            style={{ display: "flex", alignItems: "center", gap: "var(--spacing-xs)" }}
          >
            <span>💾</span>
            <span>Save Configuration</span>
          </button>
          <button
            type="button"
            onClick={() => setEditingTool(null)}
            className="btn btn-secondary"
            style={{ display: "flex", alignItems: "center", gap: "var(--spacing-xs)" }}
          >
            <span>❌</span>
            <span>Cancel</span>
          </button>
        </div>
      </form>
    );
  };

  const DatabaseConnectionForm = ({ connection = null }) => {
    const [name, setName] = useState(connection?.name || "");
    const [dbType, setDbType] = useState(connection?.db_type || "postgresql");
    const [connectionString, setConnectionString] = useState("");

    const handleSubmit = async (e) => {
      e.preventDefault();
      if (!name || (!connectionString && !connection)) {
        alert("Please fill in all required fields");
        return;
      }

      try {
        if (connection) {
          await api.updateDatabaseConnection(connection.id, {
            name: name.trim(),
            connection_string: connectionString.trim() || undefined,
          });
        } else {
          await api.createDatabaseConnection({
            name: name.trim(),
            db_type: dbType,
            connection_string: connectionString.trim(),
          });
        }
        await loadDatabaseConnections();
        setShowDatabaseForm(false);
        setEditingDatabase(null);
      } catch (e) {
        alert(`Error: ${e.message}`);
      }
    };

    const getConnectionStringPlaceholder = () => {
      switch (dbType) {
        case "postgresql":
          return "postgresql://username:password@host:port/database";
        case "mysql":
          return "mysql://username:password@host:port/database";
        case "sqlite":
          return "/path/to/database.db";
        default:
          return "Connection string";
      }
    };

    const getConnectionStringHelp = () => {
      switch (dbType) {
        case "postgresql":
          return "Format: postgresql://username:password@host:port/database";
        case "mysql":
          return "Format: mysql://username:password@host:port/database";
        case "sqlite":
          return "Path to SQLite database file (e.g., /path/to/database.db)";
        default:
          return "";
      }
    };

    return (
      <form onSubmit={handleSubmit} style={{ display: "flex", flexDirection: "column", gap: "var(--spacing-md)" }}>
        <div>
          <label style={{ display: "block", marginBottom: "var(--spacing-xs)", fontSize: "0.875rem", fontWeight: 500, color: "var(--text-primary)" }}>
            Connection Name <span style={{ color: "var(--error)" }}>*</span>
          </label>
          <input
            type="text"
            value={name}
            onChange={(e) => setName(e.target.value)}
            className="input"
            placeholder="My Database Connection"
            required
          />
        </div>

        <div>
          <label style={{ display: "block", marginBottom: "var(--spacing-xs)", fontSize: "0.875rem", fontWeight: 500, color: "var(--text-primary)" }}>
            Database Type <span style={{ color: "var(--error)" }}>*</span>
          </label>
          <select
            value={dbType}
            onChange={(e) => setDbType(e.target.value)}
            className="input"
            disabled={!!connection}
            required
          >
            <option value="postgresql">PostgreSQL</option>
            <option value="mysql">MySQL</option>
            <option value="sqlite">SQLite</option>
          </select>
          {connection && (
            <p style={{ fontSize: "0.75rem", color: "var(--text-secondary)", marginTop: "var(--spacing-xs)" }}>
              Database type cannot be changed after creation
            </p>
          )}
        </div>

        <div>
          <label style={{ display: "block", marginBottom: "var(--spacing-xs)", fontSize: "0.875rem", fontWeight: 500, color: "var(--text-primary)" }}>
            Connection String <span style={{ color: "var(--error)" }}>*</span>
          </label>
          <input
            type="password"
            value={connectionString}
            onChange={(e) => setConnectionString(e.target.value)}
            className="input"
            placeholder={getConnectionStringPlaceholder()}
            required={!connection}
          />
          <p style={{ fontSize: "0.75rem", color: "var(--text-secondary)", marginTop: "var(--spacing-xs)" }}>
            {getConnectionStringHelp()}
          </p>
          {connection && (
            <p style={{ fontSize: "0.75rem", color: "var(--text-secondary)", marginTop: "var(--spacing-xs)", fontStyle: "italic" }}>
              Leave blank to keep existing connection string, or enter a new one to update.
            </p>
          )}
        </div>

        <div style={{ display: "flex", gap: "var(--spacing-md)" }}>
          <button type="submit" className="btn btn-primary" style={{ display: "flex", alignItems: "center", gap: "var(--spacing-xs)" }}>
            <span>💾</span>
            <span>{connection ? "Update Connection" : "Create Connection"}</span>
          </button>
          <button
            type="button"
            onClick={() => {
              setShowDatabaseForm(false);
              setEditingDatabase(null);
            }}
            className="btn btn-secondary"
            style={{ display: "flex", alignItems: "center", gap: "var(--spacing-xs)" }}
          >
            <span>❌</span>
            <span>Cancel</span>
          </button>
        </div>
      </form>
    );
  };

  const handleDeleteDatabase = async (connectionId) => {
    if (!confirm("Are you sure you want to delete this database connection?")) {
      return;
    }
    try {
      await api.deleteDatabaseConnection(connectionId);
      await loadDatabaseConnections();
    } catch (e) {
      alert(`Error: ${e.message}`);
    }
  };

  const handleRefreshSchema = async (connectionId) => {
    try {
      await api.refreshDatabaseSchema(connectionId);
      await loadDatabaseConnections();
      alert("Schema refreshed successfully!");
    } catch (e) {
      alert(`Error refreshing schema: ${e.message}`);
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
          Tools Integration
        </h1>
        <p style={{ color: "var(--text-secondary)", fontSize: "0.875rem" }}>
          Connect and sync data from third-party tools to enhance your RAG search capabilities.
        </p>
      </div>

      {loading ? (
        <SkeletonLoader />
      ) : (
        <div style={{ display: "flex", flexDirection: "column", gap: "var(--spacing-lg)" }}>
          {tools.map((tool) => {
            const isConfigured = !!tool.config;
            const isActive = tool.config?.is_active;
            const syncTask = Object.values(syncTasks).find(t => t.tool_name === tool.tool_name);
            const isSyncing = syncingTools.has(tool.tool_name);

            return (
              <div key={tool.tool_name} className="card fade-in-up">
                <div style={{ display: "flex", justifyContent: "space-between", alignItems: "flex-start", marginBottom: "var(--spacing-lg)" }}>
                  <div style={{ display: "flex", alignItems: "center", gap: "var(--spacing-md)" }}>
                    <span style={{ fontSize: "2rem" }}>{tool.icon}</span>
                    <div>
                      <h2
                        style={{
                          fontSize: "1.25rem",
                          fontWeight: 600,
                          marginBottom: "var(--spacing-xs)",
                          color: "var(--text-primary)",
                        }}
                      >
                        {tool.name}
                      </h2>
                      <p style={{ color: "var(--text-secondary)", fontSize: "0.875rem" }}>
                        {tool.description}
                      </p>
                    </div>
                  </div>
                  {!tool.enabled && (
                    <span
                      style={{
                        padding: "var(--spacing-xs) var(--spacing-md)",
                        background: "var(--gray-200)",
                        color: "var(--text-secondary)",
                        borderRadius: "var(--radius-full)",
                        fontSize: "0.75rem",
                        fontWeight: 500,
                      }}
                    >
                      Coming Soon
                    </span>
                  )}
                </div>

                {tool.enabled ? (
                  <>
                    {editingTool === tool.tool_name ? (
                      <ToolConfigForm tool={tool} />
                    ) : (
                      <>
                        {isConfigured ? (
                          <div style={{ display: "flex", flexDirection: "column", gap: "var(--spacing-md)" }}>
                            <div style={{ display: "flex", alignItems: "center", gap: "var(--spacing-sm)" }}>
                              <span
                                style={{
                                  padding: "var(--spacing-xs) var(--spacing-md)",
                                  background: isActive ? "var(--success)" : "var(--gray-200)",
                                  color: isActive ? "var(--text-inverse)" : "var(--text-secondary)",
                                  borderRadius: "var(--radius-full)",
                                  fontSize: "0.75rem",
                                  fontWeight: 500,
                                }}
                              >
                                {isActive ? "✓ Configured" : "Inactive"}
                              </span>
                              {tool.config.last_sync_at && (
                                <span style={{ fontSize: "0.75rem", color: "var(--text-secondary)" }}>
                                  Last synced: {new Date(tool.config.last_sync_at).toLocaleString()}
                                </span>
                              )}
                            </div>

                            {/* Sync Status */}
                            {(isSyncing || syncTask) && (
                              <div
                                style={{
                                  padding: "var(--spacing-md)",
                                  background: "var(--gray-50)",
                                  borderRadius: "var(--radius-md)",
                                  border: "1px solid var(--gray-200)",
                                }}
                              >
                                <div style={{ display: "flex", justifyContent: "space-between", alignItems: "center", marginBottom: "var(--spacing-xs)" }}>
                                  <span style={{ fontSize: "0.875rem", fontWeight: 500 }}>
                                    {syncTask?.status === "running" ? "Syncing..." : syncTask?.status === "completed" ? "Sync Completed" : syncTask?.status === "failed" ? "Sync Failed" : "Starting sync..."}
                                  </span>
                                  {syncTask?.progress !== undefined && (
                                    <span style={{ fontSize: "0.75rem", color: "var(--text-secondary)" }}>
                                      {Math.round(syncTask.progress)}%
                                    </span>
                                  )}
                                </div>
                                {syncTask?.progress !== undefined && (
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
                                        width: `${syncTask.progress}%`,
                                        height: "100%",
                                        background: syncTask.status === "failed" ? "var(--error)" : "var(--primary)",
                                        transition: "width 0.3s ease",
                                      }}
                                    />
                                  </div>
                                )}
                                {syncTask?.message && (
                                  <p style={{ fontSize: "0.75rem", color: "var(--text-secondary)", marginTop: "var(--spacing-xs)" }}>
                                    {syncTask.message}
                                  </p>
                                )}
                                {syncTask?.error && (
                                  <p style={{ fontSize: "0.75rem", color: "var(--error)", marginTop: "var(--spacing-xs)" }}>
                                    Error: {syncTask.error}
                                  </p>
                                )}
                                {syncTask?.result && (
                                  <p style={{ fontSize: "0.75rem", color: "var(--success)", marginTop: "var(--spacing-xs)" }}>
                                    Synced {syncTask.result.tickets_synced || syncTask.result.documents_created || 0} items
                                  </p>
                                )}
                              </div>
                            )}

                            {tool.config.sync_error && (
                              <div
                                style={{
                                  padding: "var(--spacing-sm)",
                                  background: "var(--error-light)",
                                  color: "var(--error)",
                                  borderRadius: "var(--radius-md)",
                                  fontSize: "0.75rem",
                                }}
                              >
                                Last sync error: {tool.config.sync_error}
                              </div>
                            )}

                            <div style={{ display: "flex", gap: "var(--spacing-md)", flexWrap: "wrap" }}>
                              <button
                                onClick={() => handleSync(tool.tool_name)}
                                disabled={isSyncing || !isActive}
                                className="btn btn-primary"
                                style={{ display: "flex", alignItems: "center", gap: "var(--spacing-xs)" }}
                              >
                                {isSyncing ? (
                                  <>
                                    <div className="spinner" style={{ width: "1rem", height: "1rem" }} />
                                    <span>Syncing...</span>
                                  </>
                                ) : (
                                  <>
                                    <span>🔄</span>
                                    <span>Sync Now</span>
                                  </>
                                )}
                              </button>
                              <button
                                onClick={() => setEditingTool(tool.tool_name)}
                                className="btn btn-secondary"
                                style={{ display: "flex", alignItems: "center", gap: "var(--spacing-xs)" }}
                              >
                                <span>✏️</span>
                                <span>Edit</span>
                              </button>
                              <button
                                onClick={() => handleDeleteConfig(tool.tool_name)}
                                className="btn btn-danger"
                                style={{ display: "flex", alignItems: "center", gap: "var(--spacing-xs)" }}
                              >
                                <span>🗑️</span>
                                <span>Delete</span>
                              </button>
                            </div>
                          </div>
                        ) : (
                          <div>
                            <p style={{ color: "var(--text-secondary)", marginBottom: "var(--spacing-md)" }}>
                              Configure {tool.name} to start syncing data.
                            </p>
                            <button
                              onClick={() => setEditingTool(tool.tool_name)}
                              className="btn btn-primary"
                              style={{ display: "flex", alignItems: "center", gap: "var(--spacing-xs)" }}
                            >
                              <span>⚙️</span>
                              <span>Configure {tool.name}</span>
                            </button>
                          </div>
                        )}
                      </>
                    )}
                  </>
                ) : (
                  <p style={{ color: "var(--text-secondary)", fontStyle: "italic" }}>
                    This tool is not available yet. Coming soon!
                  </p>
                )}
              </div>
            );
          })}
        </div>
      )}

      {/* Database Connections Section */}
      <div style={{ marginTop: "var(--spacing-xl)", paddingTop: "var(--spacing-xl)", borderTop: "2px solid var(--gray-200)" }}>
        <div className="fade-in-down" style={{ marginBottom: "var(--spacing-xl)" }}>
          <h1
            style={{
              fontSize: "2rem",
              fontWeight: 700,
              marginBottom: "var(--spacing-sm)",
              color: "var(--text-primary)",
            }}
          >
            Database Connections
          </h1>
          <p style={{ color: "var(--text-secondary)", fontSize: "0.875rem" }}>
            Connect external databases to enable SQL queries and data analysis through natural language.
          </p>
        </div>

        {loadingDatabases ? (
          <SkeletonLoader />
        ) : (
          <div style={{ display: "flex", flexDirection: "column", gap: "var(--spacing-lg)" }}>
            {showDatabaseForm && (
              <div className="card fade-in-up">
                <h2 style={{ fontSize: "1.25rem", fontWeight: 600, marginBottom: "var(--spacing-md)", color: "var(--text-primary)" }}>
                  {editingDatabase ? "Edit Database Connection" : "Add New Database Connection"}
                </h2>
                <DatabaseConnectionForm connection={editingDatabase} />
              </div>
            )}

            {databaseConnections.map((conn) => (
              <div key={conn.id} className="card fade-in-up">
                <div style={{ display: "flex", justifyContent: "space-between", alignItems: "flex-start", marginBottom: "var(--spacing-lg)" }}>
                  <div style={{ display: "flex", alignItems: "center", gap: "var(--spacing-md)" }}>
                    <span style={{ fontSize: "2rem" }}>
                      {conn.db_type === "postgresql" ? "🐘" : conn.db_type === "mysql" ? "🐬" : "💾"}
                    </span>
                    <div>
                      <h2
                        style={{
                          fontSize: "1.25rem",
                          fontWeight: 600,
                          marginBottom: "var(--spacing-xs)",
                          color: "var(--text-primary)",
                        }}
                      >
                        {conn.name}
                      </h2>
                      <p style={{ color: "var(--text-secondary)", fontSize: "0.875rem" }}>
                        {conn.db_type.toUpperCase()} Database
                        {conn.schema_updated_at && (
                          <span style={{ marginLeft: "var(--spacing-sm)" }}>
                            • Schema updated: {new Date(conn.schema_updated_at).toLocaleString()}
                          </span>
                        )}
                      </p>
                    </div>
                  </div>
                  <span
                    style={{
                      padding: "var(--spacing-xs) var(--spacing-md)",
                      background: conn.is_active ? "var(--success)" : "var(--gray-200)",
                      color: conn.is_active ? "var(--text-inverse)" : "var(--text-secondary)",
                      borderRadius: "var(--radius-full)",
                      fontSize: "0.75rem",
                      fontWeight: 500,
                    }}
                  >
                    {conn.is_active ? "✓ Active" : "Inactive"}
                  </span>
                </div>

                {conn.schema_info && conn.schema_info.tables && (
                  <div style={{ marginBottom: "var(--spacing-md)", padding: "var(--spacing-sm)", background: "var(--gray-50)", borderRadius: "var(--radius-md)" }}>
                    <p style={{ fontSize: "0.875rem", color: "var(--text-secondary)", marginBottom: "var(--spacing-xs)" }}>
                      <strong>Schema:</strong> {conn.schema_info.tables.length} table(s) discovered
                    </p>
                    {conn.schema_info.tables.slice(0, 5).map((table) => (
                      <span
                        key={table.name}
                        style={{
                          display: "inline-block",
                          margin: "var(--spacing-xs) var(--spacing-xs) var(--spacing-xs) 0",
                          padding: "var(--spacing-xs) var(--spacing-sm)",
                          background: "var(--gray-200)",
                          borderRadius: "var(--radius-sm)",
                          fontSize: "0.75rem",
                          color: "var(--text-secondary)",
                        }}
                      >
                        {table.name} ({table.columns.length} cols)
                      </span>
                    ))}
                    {conn.schema_info.tables.length > 5 && (
                      <span style={{ fontSize: "0.75rem", color: "var(--text-secondary)", marginLeft: "var(--spacing-xs)" }}>
                        +{conn.schema_info.tables.length - 5} more
                      </span>
                    )}
                  </div>
                )}

                <div style={{ display: "flex", gap: "var(--spacing-md)", flexWrap: "wrap" }}>
                  <button
                    onClick={() => handleRefreshSchema(conn.id)}
                    className="btn btn-secondary"
                    style={{ display: "flex", alignItems: "center", gap: "var(--spacing-xs)" }}
                  >
                    <span>🔄</span>
                    <span>Refresh Schema</span>
                  </button>
                  <button
                    onClick={() => {
                      setEditingDatabase(conn);
                      setShowDatabaseForm(true);
                    }}
                    className="btn btn-secondary"
                    style={{ display: "flex", alignItems: "center", gap: "var(--spacing-xs)" }}
                  >
                    <span>✏️</span>
                    <span>Edit</span>
                  </button>
                  <button
                    onClick={() => handleDeleteDatabase(conn.id)}
                    className="btn btn-danger"
                    style={{ display: "flex", alignItems: "center", gap: "var(--spacing-xs)" }}
                  >
                    <span>🗑️</span>
                    <span>Delete</span>
                  </button>
                </div>
              </div>
            ))}

            {!showDatabaseForm && databaseConnections.length === 0 && (
              <div className="card fade-in-up">
                <p style={{ color: "var(--text-secondary)", marginBottom: "var(--spacing-md)" }}>
                  No database connections configured. Add one to start querying your databases with natural language.
                </p>
                <button
                  onClick={() => setShowDatabaseForm(true)}
                  className="btn btn-primary"
                  style={{ display: "flex", alignItems: "center", gap: "var(--spacing-xs)" }}
                >
                  <span>➕</span>
                  <span>Add Database Connection</span>
                </button>
              </div>
            )}

            {!showDatabaseForm && databaseConnections.length > 0 && (
              <button
                onClick={() => setShowDatabaseForm(true)}
                className="btn btn-primary"
                style={{ display: "flex", alignItems: "center", gap: "var(--spacing-xs)", alignSelf: "flex-start" }}
              >
                <span>➕</span>
                <span>Add Another Database Connection</span>
              </button>
            )}
          </div>
        )}
      </div>
    </div>
  );
};

export default ToolsPage;

