const API_BASE =
  process.env.NEXT_PUBLIC_API_BASE_URL ||
  "https://discord-ai-bot-1-p5hk.onrender.com";

function getToken() {
  if (typeof window === "undefined") {
    return null;
  }

  return localStorage.getItem("token");
}

export function getStoredUser() {
  if (typeof window === "undefined") {
    return null;
  }

  const raw = localStorage.getItem("dashboard_user");
  if (!raw) {
    return null;
  }

  try {
    return JSON.parse(raw);
  } catch {
    return null;
  }
}

async function apiFetch(endpoint, options = {}) {
  const token = getToken();
  const headers = {
    ...(options.body ? { "Content-Type": "application/json" } : {}),
    ...(token ? { Authorization: `Bearer ${token}` } : {}),
    ...(options.headers || {}),
  };

  const res = await fetch(`${API_BASE}${endpoint}`, {
    ...options,
    headers,
  });

  if (res.status === 401) {
    if (typeof window !== "undefined") {
      localStorage.removeItem("token");
      window.location.href = "/login";
    }
    throw new Error("Unauthorized");
  }

  if (!res.ok) {
    const text = await res.text();
    throw new Error(text || "API error");
  }

  return res.json();
}

export function getApiBase() {
  return API_BASE;
}

export function getServers() {
  return apiFetch("/api/server_map");
}

export function getTickets() {
  return apiFetch("/api/tickets");
}

export function getOverview() {
  return apiFetch("/api/overview");
}

export function getConversation(ticketId) {
  return apiFetch(`/api/conversation/${ticketId}`);
}

export function claimTicket(ticketId) {
  return apiFetch(`/api/tickets/${ticketId}/claim`, {
    method: "POST",
  });
}

export function updateTicketMeta(ticketId, payload) {
  return apiFetch(`/api/tickets/${ticketId}/meta`, {
    method: "POST",
    body: JSON.stringify(payload),
  });
}

export function addInternalNote(ticketId, note) {
  return apiFetch(`/api/tickets/${ticketId}/notes`, {
    method: "POST",
    body: JSON.stringify({ note }),
  });
}

export function handoffTicket(ticketId, assignedTo, note) {
  return apiFetch(`/api/tickets/${ticketId}/handoff`, {
    method: "POST",
    body: JSON.stringify({
      assigned_to: assignedTo,
      note,
    }),
  });
}

export function suggestReply(ticketId) {
  return apiFetch("/api/ai/suggest", {
    method: "POST",
    body: JSON.stringify({ ticket_id: ticketId }),
  });
}

export function sendReply(ticketId, message) {
  return apiFetch("/api/send_reply", {
    method: "POST",
    body: JSON.stringify({
      ticket_id: ticketId,
      message,
    }),
  });
}

export function closeTicket(ticketId) {
  return apiFetch("/api/close_ticket", {
    method: "POST",
    body: JSON.stringify({
      ticket_id: ticketId,
    }),
  });
}

export function bulkCloseTickets(ticketIds) {
  return apiFetch("/api/tickets/bulk_close", {
    method: "POST",
    body: JSON.stringify({
      ticket_ids: ticketIds,
    }),
  });
}

export function getAdminLogs() {
  return apiFetch("/api/admin_logs");
}

export function getAlerts() {
  return apiFetch("/api/alerts");
}

export function logout() {
  if (typeof window !== "undefined") {
    localStorage.removeItem("token");
    localStorage.removeItem("dashboard_user");
    window.location.href = "/login";
  }
}

export async function login(username, password) {
  const res = await fetch(`${API_BASE}/api/login`, {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({ username, password }),
  });

  const data = await res.json();

  if (data.access_token && typeof window !== "undefined") {
    localStorage.setItem("token", data.access_token);
    localStorage.setItem("dashboard_user", JSON.stringify(data.user || null));
  }

  return data;
}
