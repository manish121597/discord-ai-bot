const API_BASE = "https://discord-ai-bot-1-p5hk.onrender.com";

console.log("API_BASE:", API_BASE);

export async function getServers() {
  const res = await fetch(`${API_BASE}/api/server_map`, {
    headers: { Authorization: `Bearer ${localStorage.getItem("token")}` },
  });
  return res.json();
}

export async function getConversation(ticketId) {
  const res = await fetch(`${API_BASE}/api/conversation/${ticketId}`, {
    headers: { Authorization: `Bearer ${localStorage.getItem("token")}` },
  });
  return res.json();
}

export async function getTickets() {
  const res = await fetch(`${API_BASE}/api/tickets`, {
    headers: { Authorization: `Bearer ${localStorage.getItem("token")}` },
  });
  return res.json();
}

export async function sendReply(ticketId, message) {
  const res = await fetch(`${API_BASE}/api/send_reply`, {
    method: "POST",
    headers: {
      "Content-Type": "application/json",
      Authorization: `Bearer ${localStorage.getItem("token")}`,
    },
    body: JSON.stringify({ ticket_id: ticketId, message }),
  });
  return res.json();
}

export async function closeTicket(ticketId) {
  const res = await fetch(`${API_BASE}/api/close_ticket`, {
    method: "POST",
    headers: {
      "Content-Type": "application/json",
      Authorization: `Bearer ${localStorage.getItem("token")}`,
    },
    body: JSON.stringify({ ticket_id: ticketId }),
  });
  return res.json();
}

export async function getAdminLogs() {
  const res = await fetch(`${API_BASE}/api/admin_logs`, {
    headers: { Authorization: `Bearer ${localStorage.getItem("token")}` },
  });
  return res.json();
}

export async function login(username, password) {
  const res = await fetch(`${API_BASE}/api/login`, {
    method: "POST",
    headers: {"Content-Type": "application/json"},
    body: JSON.stringify({ username, password }),
  });
  const data = await res.json();
  localStorage.setItem("token", data.access_token);
  return data;
}