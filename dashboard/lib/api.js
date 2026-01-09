const API_BASE = process.env.NEXT_PUBLIC_API_URL;

export async function getServers() {
  try {
    const res = await fetch(`${API_BASE}/api/server_map`);
    return await res.json();
  } catch {
    return { servers: [] };
  }
}

export async function getConversation(ticketId) {
  try {
    const res = await fetch(`${API_BASE}/api/conversation/${ticketId}`);
    return await res.json();
  } catch {
    return { messages: [] };
  }
}
