export async function getServers() {
  try {
    const res = await fetch("http://127.0.0.1:8081/api/server_map");
    return await res.json();
  } catch {
    return { servers: [] };
  }
}

export async function getConversation(ticketId) {
  try {
    const res = await fetch(`http://127.0.0.1:8081/api/conversation/${ticketId}`);
    return await res.json();
  } catch {
    return { messages: [] };
  }
}
