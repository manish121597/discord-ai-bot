const API_BASE = "https://discord-ai-bot-1-p5hk.onrender.com";

// 🔐 GET TOKEN
function getToken() {
  return localStorage.getItem("token");
}

// 🚀 CORE FETCH WRAPPER
async function apiFetch(endpoint, options = {}) {
  const token = getToken();

  const res = await fetch(${API_BASE}${endpoint}, {
    ...options,
    headers: {
      "Content-Type": "application/json",
      Authorization: Bearer ${token}, // ✅ FIXED
      ...(options.headers || {}),
    },
  });

  // ❌ handle unauthorized
  if (res.status === 401) {
    localStorage.removeItem("token");
    window.location.href = "/login";
    return;
  }

  // ❌ handle errors
  if (!res.ok) {
    const text = await res.text();
    throw new Error(text || "API error");
  }

  return res.json();
}

// 📡 APIs

export function getServers() {
  return apiFetch("/api/server_map");
}

export function getTickets() {
  return apiFetch("/api/tickets");
}

export function getConversation(ticketId) {
  return apiFetch(/api/conversation/${ticketId});
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

export function getAdminLogs() {
  return apiFetch("/api/admin_logs");
}

// 🔐 LOGIN
export async function login(username, password) {
  const res = await fetch(${API_BASE}/api/login, {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({ username, password }),
  });

  const data = await res.json();

  if (data.access_token) {
    localStorage.setItem("token", data.access_token);
  }

  return data;
}