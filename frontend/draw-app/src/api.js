const API_BASE = "/api/drawings";

async function fetchAPI(path, options = {}) {
  const res = await fetch(`${API_BASE}${path}`, {
    credentials: "include",
    headers: { "Content-Type": "application/json", ...options.headers },
    ...options,
  });
  if (!res.ok) {
    const data = await res.json().catch(() => ({}));
    throw new Error(data.detail || `API error ${res.status}`);
  }
  if (res.status === 204) return null;
  return res.json();
}

export const drawingsAPI = {
  list: () => fetchAPI(""),
  get: (id) => fetchAPI(`/${id}`),
  getShared: (shareId) => fetchAPI(`/shared/${shareId}`),
  create: (data) =>
    fetchAPI("", { method: "POST", body: JSON.stringify(data) }),
  update: (id, data) =>
    fetchAPI(`/${id}`, { method: "PUT", body: JSON.stringify(data) }),
  delete: (id) => fetchAPI(`/${id}`, { method: "DELETE" }),
};

export async function checkAuth() {
  try {
    const res = await fetch("/api/auth/me", { credentials: "include" });
    if (res.ok) return await res.json();
    return null;
  } catch {
    return null;
  }
}
