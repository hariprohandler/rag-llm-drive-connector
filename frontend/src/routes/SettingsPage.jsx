import React, { useEffect, useState } from "react";
import { api } from "../api.js";

const SkeletonLoader = () => (
  <div className="card">
    <div className="skeleton skeleton-title" />
    <div className="skeleton skeleton-text" />
    <div className="skeleton skeleton-text" style={{ width: "80%" }} />
  </div>
);

const SettingsPage = () => {
  const [configs, setConfigs] = useState([]);
  const [selectedProvider, setSelectedProvider] = useState("openai");
  const [apiKey, setApiKey] = useState("");
  const [modelName, setModelName] = useState("");
  const [baseUrl, setBaseUrl] = useState("");
  const [temperature, setTemperature] = useState("0");
  const [maxTokens, setMaxTokens] = useState("");
  const [isDefault, setIsDefault] = useState(false);
  const [saving, setSaving] = useState(false);
  const [loading, setLoading] = useState(true);
  const [editingId, setEditingId] = useState(null);

  const providerConfigs = {
    openai: {
      name: "OpenAI",
      models: ["gpt-4o", "gpt-4o-mini", "gpt-4-turbo", "gpt-3.5-turbo"],
      defaultModel: "gpt-4o-mini",
      requiresApiKey: true,
      requiresBaseUrl: false,
    },
    gemini: {
      name: "Google Gemini",
      models: ["gemini-pro", "gemini-pro-vision", "gemini-1.5-pro", "gemini-1.5-flash"],
      defaultModel: "gemini-pro",
      requiresApiKey: true,
      requiresBaseUrl: false,
    },
    anthropic: {
      name: "Anthropic Claude",
      models: ["claude-3-opus-20240229", "claude-3-sonnet-20240229", "claude-3-haiku-20240307", "claude-3-5-sonnet-20241022"],
      defaultModel: "claude-3-sonnet-20240229",
      requiresApiKey: true,
      requiresBaseUrl: false,
    },
    custom: {
      name: "Self-Hosted / Custom",
      models: ["llama-2", "llama-3", "mistral", "custom"],
      defaultModel: "custom",
      requiresApiKey: false,
      requiresBaseUrl: true,
    },
  };

  const loadConfigs = async () => {
    try {
      setLoading(true);
      const data = await api.listLLMConfigs();
      setConfigs(data);
    } catch (e) {
      console.error("Failed to load configs:", e);
    } finally {
      setLoading(false);
    }
  };

  useEffect(() => {
    loadConfigs();
  }, []);

  useEffect(() => {
    const config = providerConfigs[selectedProvider];
    if (config && !modelName) {
      setModelName(config.defaultModel);
    }
  }, [selectedProvider]);

  const resetForm = () => {
    setApiKey("");
    setModelName("");
    setBaseUrl("");
    setTemperature("0");
    setMaxTokens("");
    setIsDefault(false);
    setEditingId(null);
    const config = providerConfigs[selectedProvider];
    if (config) {
      setModelName(config.defaultModel);
    }
  };

  const handleEdit = (config) => {
    setEditingId(config.id);
    setSelectedProvider(config.provider);
    setApiKey(config.api_key ? "••••••••" : "");
    setModelName(config.model_name || "");
    setBaseUrl(config.base_url || "");
    setTemperature(config.temperature || "0");
    setMaxTokens(config.max_tokens?.toString() || "");
    setIsDefault(config.is_default || false);
  };

  const handleSave = async () => {
    const provider = providerConfigs[selectedProvider];
    if (provider.requiresApiKey && !apiKey.trim() && apiKey !== "••••••••") {
      alert("Please enter an API key.");
      return;
    }
    if (provider.requiresBaseUrl && !baseUrl.trim()) {
      alert("Please enter a base URL for the self-hosted model.");
      return;
    }
    if (!modelName.trim()) {
      alert("Please select or enter a model name.");
      return;
    }

    setSaving(true);
    try {
      const configData = {
        provider: selectedProvider,
        api_key: apiKey === "••••••••" ? undefined : apiKey,
        model_name: modelName,
        base_url: baseUrl || undefined,
        temperature: temperature,
        max_tokens: maxTokens ? parseInt(maxTokens) : undefined,
        is_default: isDefault,
      };

      if (editingId) {
        await api.updateLLMConfig(editingId, configData);
      } else {
        await api.createLLMConfig(configData);
      }
      resetForm();
      await loadConfigs();
    } catch (e) {
      alert(`Error: ${e.message}`);
    } finally {
      setSaving(false);
    }
  };

  const handleDelete = async (configId) => {
    if (!confirm("Are you sure you want to delete this configuration?")) {
      return;
    }
    try {
      await api.deleteLLMConfig(configId);
      await loadConfigs();
      if (editingId === configId) {
        resetForm();
      }
    } catch (e) {
      alert(`Error: ${e.message}`);
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
          LLM Settings
        </h1>
        <p style={{ color: "var(--text-secondary)", fontSize: "0.875rem" }}>
          Configure Large Language Model providers for the RAG pipeline. Support for OpenAI, Gemini, Anthropic, and self-hosted models.
        </p>
      </div>

      {loading ? (
        <SkeletonLoader />
      ) : (
        <>
          {/* Create/Edit Configuration Form */}
          <div className="card fade-in-up" style={{ marginBottom: "var(--spacing-xl)" }}>
            <h2
              style={{
                fontSize: "1.25rem",
                fontWeight: 600,
                marginBottom: "var(--spacing-lg)",
                color: "var(--text-primary)",
              }}
            >
              {editingId ? "Edit Configuration" : "Create New Configuration"}
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
                  Provider
                </label>
                <select
                  value={selectedProvider}
                  onChange={(e) => {
                    setSelectedProvider(e.target.value);
                    const config = providerConfigs[e.target.value];
                    if (config) {
                      setModelName(config.defaultModel);
                    }
                  }}
                  className="input"
                  disabled={!!editingId}
                >
                  {Object.entries(providerConfigs).map(([key, config]) => (
                    <option key={key} value={key}>
                      {config.name}
                    </option>
                  ))}
                </select>
              </div>

              {providerConfigs[selectedProvider].requiresApiKey && (
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
                    API Key {editingId && apiKey === "••••••••" && "(leave blank to keep current)"}
                  </label>
                  <input
                    type="password"
                    value={apiKey}
                    onChange={(e) => setApiKey(e.target.value)}
                    className="input"
                    placeholder={selectedProvider === "openai" ? "sk-..." : "Enter API key"}
                  />
                </div>
              )}

              {providerConfigs[selectedProvider].requiresBaseUrl && (
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
                    Base URL
                  </label>
                  <input
                    type="text"
                    value={baseUrl}
                    onChange={(e) => setBaseUrl(e.target.value)}
                    className="input"
                    placeholder="http://localhost:8000/v1 or https://your-llm-server.com/v1"
                  />
                  <p style={{ fontSize: "0.75rem", color: "var(--text-secondary)", marginTop: "var(--spacing-xs)" }}>
                    For self-hosted models (Llama, Mistral, etc.), provide the API endpoint URL
                  </p>
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
                  Model
                </label>
                {selectedProvider === "custom" ? (
                  <input
                    type="text"
                    value={modelName}
                    onChange={(e) => setModelName(e.target.value)}
                    className="input"
                    placeholder="e.g., llama-2-7b, mistral-7b"
                  />
                ) : (
                  <select
                    value={modelName}
                    onChange={(e) => setModelName(e.target.value)}
                    className="input"
                  >
                    {providerConfigs[selectedProvider].models.map((model) => (
                      <option key={model} value={model}>
                        {model}
                      </option>
                    ))}
                  </select>
                )}
              </div>

              <div style={{ display: "grid", gridTemplateColumns: "1fr 1fr", gap: "var(--spacing-md)" }}>
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
                    Temperature
                  </label>
                  <input
                    type="number"
                    min="0"
                    max="2"
                    step="0.1"
                    value={temperature}
                    onChange={(e) => setTemperature(e.target.value)}
                    className="input"
                    placeholder="0"
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
                    Max Tokens (optional)
                  </label>
                  <input
                    type="number"
                    min="1"
                    value={maxTokens}
                    onChange={(e) => setMaxTokens(e.target.value)}
                    className="input"
                    placeholder="4096"
                  />
                </div>
              </div>

              <div style={{ display: "flex", alignItems: "center", gap: "var(--spacing-sm)" }}>
                <input
                  type="checkbox"
                  id="isDefault"
                  checked={isDefault}
                  onChange={(e) => setIsDefault(e.target.checked)}
                />
                <label htmlFor="isDefault" style={{ fontSize: "0.875rem", color: "var(--text-primary)" }}>
                  Set as default configuration
                </label>
              </div>

              <div style={{ display: "flex", gap: "var(--spacing-md)" }}>
                <button
                  onClick={handleSave}
                  disabled={saving}
                  className="btn btn-primary hover-lift"
                >
                  {saving ? (
                    <>
                      <div className="spinner" style={{ width: "1rem", height: "1rem" }} />
                      Saving...
                    </>
                  ) : editingId ? (
                    "Update Configuration"
                  ) : (
                    "Create Configuration"
                  )}
                </button>
                {editingId && (
                  <button
                    onClick={resetForm}
                    className="btn btn-secondary"
                    disabled={saving}
                  >
                    Cancel
                  </button>
                )}
              </div>
            </div>
          </div>

          {/* Existing Configurations */}
          <div className="card fade-in-up">
            <h2
              style={{
                fontSize: "1.25rem",
                fontWeight: 600,
                marginBottom: "var(--spacing-lg)",
                color: "var(--text-primary)",
              }}
            >
              Existing Configurations
            </h2>
            {configs.length === 0 ? (
              <p style={{ color: "var(--text-secondary)" }}>No configurations yet. Create one above.</p>
            ) : (
              <div style={{ display: "flex", flexDirection: "column", gap: "var(--spacing-sm)" }}>
                {configs.map((c, i) => (
                  <div
                    key={c.id}
                    className="fade-in-up hover-lift"
                    style={{
                      padding: "var(--spacing-md)",
                      background: "var(--gray-50)",
                      borderRadius: "var(--radius-md)",
                      display: "flex",
                      alignItems: "center",
                      justifyContent: "space-between",
                      animationDelay: `${i * 0.1}s`,
                      transition: "all var(--transition-base)",
                    }}
                  >
                    <div style={{ flex: 1 }}>
                      <div style={{ fontWeight: 600, marginBottom: "var(--spacing-xs)" }}>
                        {providerConfigs[c.provider]?.name || c.provider} – {c.model_name || "default"}
                      </div>
                      <div style={{ fontSize: "0.875rem", color: "var(--text-secondary)" }}>
                        ID: {c.id} • Temperature: {c.temperature || "0"}
                        {c.max_tokens && ` • Max Tokens: ${c.max_tokens}`}
                        {c.base_url && ` • Base URL: ${c.base_url}`}
                      </div>
                    </div>
                    <div style={{ display: "flex", alignItems: "center", gap: "var(--spacing-md)" }}>
                      {c.is_default && (
                        <span
                          className="pulse-notification"
                          style={{
                            padding: "var(--spacing-xs) var(--spacing-sm)",
                            background: "var(--success)",
                            color: "var(--text-inverse)",
                            borderRadius: "var(--radius-full)",
                            fontSize: "0.75rem",
                            fontWeight: 500,
                          }}
                        >
                          Default
                        </span>
                      )}
                      <button
                        onClick={() => handleEdit(c)}
                        className="btn btn-secondary"
                        style={{ padding: "var(--spacing-xs) var(--spacing-md)", fontSize: "0.875rem" }}
                      >
                        Edit
                      </button>
                      <button
                        onClick={() => handleDelete(c.id)}
                        className="btn btn-danger"
                        style={{ padding: "var(--spacing-xs) var(--spacing-md)", fontSize: "0.875rem" }}
                      >
                        Delete
                      </button>
                    </div>
                  </div>
                ))}
              </div>
            )}
          </div>
        </>
      )}
    </div>
  );
};

export default SettingsPage;
