// Get backend URL from environment variable (Vite uses import.meta.env)
export const BACKEND_BASE_URL = import.meta.env.VITE_BACKEND_BASE_URL || "http://localhost:8000";

// Generate or retrieve tracingId from sessionStorage
function getTracingId() {
  let tracingId = sessionStorage.getItem("tracingId");
  if (!tracingId) {
    // Generate a new tracingId (UUID v4 format)
    tracingId = crypto.randomUUID ? crypto.randomUUID() : generateUUID();
    sessionStorage.setItem("tracingId", tracingId);
  }
  return tracingId;
}

// Fallback UUID generator for browsers without crypto.randomUUID
function generateUUID() {
  return 'xxxxxxxx-xxxx-4xxx-yxxx-xxxxxxxxxxxx'.replace(/[xy]/g, function(c) {
    const r = Math.random() * 16 | 0;
    const v = c === 'x' ? r : (r & 0x3 | 0x8);
    return v.toString(16);
  });
}

async function request(path, options = {}) {
  const tracingId = getTracingId();
  const res = await fetch(`${BACKEND_BASE_URL}${path}`, {
    credentials: "include", // send cookies
    headers: {
      "Content-Type": "application/json",
      "X-Tracing-Id": tracingId,
      ...(options.headers || {})
    },
    ...options
  });

  if (!res.ok) {
    let errorMessage = res.statusText;
    try {
      const errorData = await res.json();
      errorMessage = JSON.stringify(errorData);
    } catch {
      // If response is not JSON, try to get text
      try {
        const text = await res.text();
        errorMessage = text || res.statusText;
      } catch {
        errorMessage = res.statusText;
      }
    }
    throw new Error(errorMessage);
  }
  return res.json();
}

export const api = {
  me: () => request("/auth/me"),
  sendChatMessage: async (body, onStream) => {
    // Check if streaming is requested (default: true)
    const stream = body.stream !== false;
    const url = `${BACKEND_BASE_URL}/api/chat/messages${stream ? '?stream=true' : ''}`;
    
    if (stream && onStream) {
      // Use EventSource for Server-Sent Events
      const response = await fetch(url, {
        method: "POST",
        credentials: "include",
        headers: {
          "Content-Type": "application/json",
          "X-Tracing-Id": getTracingId(),
        },
        body: JSON.stringify({ ...body, stream: undefined }),
      });

      if (!response.ok) {
        const errorText = await response.text();
        throw new Error(errorText || "Request failed");
      }

      const reader = response.body.getReader();
      const decoder = new TextDecoder();
      let buffer = "";

      while (true) {
        const { done, value } = await reader.read();
        if (done) break;

        buffer += decoder.decode(value, { stream: true });
        const lines = buffer.split("\n\n");
        buffer = lines.pop() || ""; // Keep incomplete line in buffer

        for (const line of lines) {
          if (line.startsWith("data: ")) {
            try {
              const data = JSON.parse(line.slice(6));
              onStream(data);
            } catch (e) {
              console.error("Error parsing SSE data:", e);
            }
          }
        }
      }
      return {}; // Streaming handled via callbacks
    } else {
      // Non-streaming fallback
      return request("/api/chat/messages", { method: "POST", body: JSON.stringify(body) });
    }
  },
  listLLMConfigs: (includeInactive = true) => request(`/api/llm-configs?include_inactive=${includeInactive}`),
  createLLMConfig: (body) =>
    request("/api/llm-configs", { method: "POST", body: JSON.stringify(body) }),
  updateLLMConfig: (configId, body) =>
    request(`/api/llm-configs/${configId}`, { method: "PUT", body: JSON.stringify(body) }),
  toggleLLMConfigActive: (configId, isActive) =>
    request(`/api/llm-configs/${configId}`, { method: "PUT", body: JSON.stringify({ is_active: isActive }) }),
  deleteLLMConfig: (configId) =>
    request(`/api/llm-configs/${configId}`, { method: "DELETE" }),
  getOrganizationSettings: () => request("/api/settings/organization"),
  updateOrganizationSettings: (body) =>
    request("/api/settings/organization", { method: "PUT", body: JSON.stringify(body) }),
  ingestGoogleDrive: (body) =>
    request("/api/ingest/google-drive", { method: "POST", body: JSON.stringify(body) }),
  ingestOneDrive: (body) =>
    request("/api/ingest/onedrive", { method: "POST", body: JSON.stringify(body) }),
  // Drive connection and file browsing
  connectGoogleDrive: () => window.location.href = `${BACKEND_BASE_URL}/api/drive/connect/google`,
  connectMicrosoftOneDrive: () => window.location.href = `${BACKEND_BASE_URL}/api/drive/connect/microsoft`,
  checkGoogleDriveStatus: () => request("/api/drive/status/google"),
  checkMicrosoftOneDriveStatus: () => request("/api/drive/status/microsoft"),
  listGoogleFiles: (folderId, pageToken) => {
    const params = new URLSearchParams();
    if (folderId) params.append("folder_id", folderId);
    if (pageToken) params.append("page_token", pageToken);
    return request(`/api/drive/files/google?${params.toString()}`);
  },
  listMicrosoftFiles: (folderPath, pageToken) => {
    const params = new URLSearchParams();
    params.append("folder_path", folderPath || "/");
    if (pageToken) params.append("page_token", pageToken);
    return request(`/api/drive/files/microsoft?${params.toString()}`);
  },
  startGoogleIngestion: (body) =>
    request("/api/drive/ingest/google", { method: "POST", body: JSON.stringify(body) }),
  startMicrosoftIngestion: (body) =>
    request("/api/drive/ingest/microsoft", { method: "POST", body: JSON.stringify(body) }),
  getIngestionTaskStatus: async (taskId) => {
    try {
      return await request(`/api/drive/task/${taskId}`);
    } catch (e) {
      // Fallback to ingest task endpoint for file uploads
      return await request(`/api/ingest/task/${taskId}`);
    }
  },
  listLocalFiles: () => request("/api/knowledge-bases/local/files"),
  // Chat conversations
  listConversations: () => request("/api/chat/conversations"),
  getConversation: (conversationId) => request(`/api/chat/conversations/${conversationId}`),
  createConversation: (body) => request("/api/chat/conversations", { method: "POST", body: JSON.stringify(body) }),
  deleteConversation: (conversationId) => request(`/api/chat/conversations/${conversationId}`, { method: "DELETE" }),
  // Knowledge bases (for file tracking)
  listKnowledgeBases: (includeSyncHistory = false) => {
    const params = includeSyncHistory ? "?include_sync_history=true" : "";
    return request(`/api/knowledge-bases${params}`);
  },
  getKnowledgeBase: (kbId) => request(`/api/knowledge-bases/${kbId}`),
  deleteKnowledgeBase: (kbId) => request(`/api/knowledge-bases/${kbId}`, { method: "DELETE" }),
  // Tools integration
  listTools: () => request("/api/tools"),
  getToolConfig: (toolName) => request(`/api/tools/${toolName}`),
  createToolConfig: (body) => request("/api/tools", { method: "POST", body: JSON.stringify(body) }),
  updateToolConfig: (toolName, body) => request(`/api/tools/${toolName}`, { method: "PUT", body: JSON.stringify(body) }),
  deleteToolConfig: (toolName) => request(`/api/tools/${toolName}`, { method: "DELETE" }),
  syncTool: (body) => request("/api/tools/sync", { method: "POST", body: JSON.stringify(body) }),
  getSyncStatus: (taskId) => request(`/api/tools/sync/${taskId}`),
  // Database connections
  listDatabaseConnections: () => request("/api/databases/connections"),
  getDatabaseConnection: (connectionId) => request(`/api/databases/connections/${connectionId}`),
  createDatabaseConnection: (body) => request("/api/databases/connections", { method: "POST", body: JSON.stringify(body) }),
  updateDatabaseConnection: (connectionId, body) => request(`/api/databases/connections/${connectionId}`, { method: "PUT", body: JSON.stringify(body) }),
  deleteDatabaseConnection: (connectionId) => request(`/api/databases/connections/${connectionId}`, { method: "DELETE" }),
  refreshDatabaseSchema: (connectionId) => request(`/api/databases/connections/${connectionId}/refresh-schema`, { method: "POST" }),
  executeSQLQuery: (body) => request("/api/databases/query", { method: "POST", body: JSON.stringify(body) }),
};


