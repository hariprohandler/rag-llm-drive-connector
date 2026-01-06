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
  listLLMConfigs: () => request("/api/llm-configs"),
  createLLMConfig: (body) =>
    request("/api/llm-configs", { method: "POST", body: JSON.stringify(body) }),
  updateLLMConfig: (configId, body) =>
    request(`/api/llm-configs/${configId}`, { method: "PUT", body: JSON.stringify(body) }),
  deleteLLMConfig: (configId) =>
    request(`/api/llm-configs/${configId}`, { method: "DELETE" }),
  getOrganizationSettings: () => request("/api/settings/organization"),
  updateOrganizationSettings: (body) =>
    request("/api/settings/organization", { method: "PUT", body: JSON.stringify(body) }),
};


