import React, { useEffect, useState } from "react";
import { api } from "../api.js";

const SettingsPage = () => {
  const [configs, setConfigs] = useState([]);
  const [apiKey, setApiKey] = useState("");
  const [modelName, setModelName] = useState("gpt-4o-mini");
  const [saving, setSaving] = useState(false);

  const loadConfigs = async () => {
    try {
      const data = await api.listLLMConfigs();
      setConfigs(data);
    } catch (e) {
      console.error(e);
    }
  };

  useEffect(() => {
    loadConfigs();
  }, []);

  const saveOpenAIConfig = async () => {
    if (!apiKey) {
      alert("Please enter an API key.");
      return;
    }
    setSaving(true);
    try {
      await api.createLLMConfig({
        provider: "openai",
        api_key: apiKey,
        model_name: modelName,
        is_default: true
      });
      setApiKey("");
      await loadConfigs();
    } catch (e) {
      alert(e.message);
    } finally {
      setSaving(false);
    }
  };

  return (
    <div>
      <h1>LLM Settings</h1>
      <section style={{ marginBottom: 24 }}>
        <h2>OpenAI Configuration</h2>
        <div style={{ marginBottom: 8 }}>
          <label style={{ display: "block", marginBottom: 4 }}>API Key</label>
          <input
            type="password"
            value={apiKey}
            onChange={(e) => setApiKey(e.target.value)}
            style={{ width: "100%" }}
          />
        </div>
        <div style={{ marginBottom: 8 }}>
          <label style={{ display: "block", marginBottom: 4 }}>Model</label>
          <select
            value={modelName}
            onChange={(e) => setModelName(e.target.value)}
          >
            <option value="gpt-4o-mini">gpt-4o-mini</option>
            <option value="gpt-4o">gpt-4o</option>
            <option value="gpt-3.5-turbo">gpt-3.5-turbo</option>
          </select>
        </div>
        <button onClick={saveOpenAIConfig} disabled={saving}>
          {saving ? "Saving..." : "Save OpenAI Config"}
        </button>
      </section>

      <section>
        <h2>Existing Configurations</h2>
        {configs.length === 0 && <p>No configurations yet.</p>}
        <ul>
          {configs.map((c) => (
            <li key={c.id}>
              {c.provider} – {c.model_name || "default"}{" "}
              {c.is_default ? "(default)" : ""}
            </li>
          ))}
        </ul>
      </section>
    </div>
  );
};

export default SettingsPage;


