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
    const text = await res.text();
    throw new Error(text || res.statusText);
  }
  return res.json();
}

export const api = {
  me: () => request("/auth/me"),
  sendChatMessage: (body) =>
    request("/api/chat/messages", { method: "POST", body: JSON.stringify(body) }),
  listLLMConfigs: () => request("/api/llm-configs"),
  createLLMConfig: (body) =>
    request("/api/llm-configs", { method: "POST", body: JSON.stringify(body) })
  // You can add update/delete configs and ingest endpoints as needed.
};


