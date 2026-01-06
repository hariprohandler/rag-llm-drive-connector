// Get backend URL from environment variable (Vite uses import.meta.env)
export const BACKEND_BASE_URL = import.meta.env.VITE_BACKEND_BASE_URL || "http://localhost:8000";

async function request(path, options = {}) {
  const res = await fetch(`${BACKEND_BASE_URL}${path}`, {
    credentials: "include", // send cookies
    headers: {
      "Content-Type": "application/json",
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
  sendChatMessage: (body) =>
    request("/api/chat/messages", { method: "POST", body: JSON.stringify(body) }),
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
  getIngestionTaskStatus: (taskId) =>
    request(`/api/drive/task/${taskId}`),
};


