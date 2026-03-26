"use client";

import { useState, useEffect } from "react";
import { useRouter } from "next/navigation";

const BASE = "https://discord-ai-bot-1-p5hk.onrender.com";

export default function Dashboard() {
  const router = useRouter();

  const [servers, setServers] = useState([]);
  const [tickets, setTickets] = useState([]);
  const [loading, setLoading] = useState(true);

  // 🔒 Auth check + auto load
  useEffect(() => {
    const token = localStorage.getItem("token");
    if (!token) {
      router.push("/login");
      return;
    }

    loadAll();
  }, []);

  async function loadAll() {
    setLoading(true);
    await Promise.all([loadServers(), loadTickets()]);
    setLoading(false);
  }

  async function loadServers() {
    try {
      const token = localStorage.getItem("token");

      const res = await fetch(${BASE}/api/server_map, {
        headers: {
          Authorization: Bearer ${token},
        },
      });

      const data = await res.json();
      setServers(data.servers || []);
    } catch (err) {
      console.error("Server load error:", err);
    }
  }

  async function loadTickets() {
    try {
      const token = localStorage.getItem("token");

      const res = await fetch(${BASE}/api/tickets, {
        headers: {
          Authorization: Bearer ${token},
        },
      });

      const data = await res.json();
      setTickets(data.tickets || []);
    } catch (err) {
      console.error("Ticket load error:", err);
    }
  }

  // 👉 open ticket page
  function openTicket(id) {
    router.push(/tickets/${id});
  }

  return (
    <div className="min-h-screen bg-black text-yellow-400 p-10">
      <h1 className="text-4xl font-bold mb-10">
        ⚡ Donde Ticket Manager — Admin Dashboard
      </h1>

      {loading && (
        <p className="text-yellow-500 mb-6">Loading data...</p>
      )}

      {/* SERVER MAP */}
      <div className="bg-neutral-900 p-6 rounded-xl border border-yellow-700 mb-10">
        <h2 className="text-2xl mb-4">Server Map</h2>

        <div className="grid gap-4">
          {servers.map((server) => (
            <div
              key={server.id}
              className="p-4 bg-neutral-800 rounded-lg border border-yellow-600"
            >
              <p className="text-lg font-bold">{server.name}</p>
              <p className="text-sm text-yellow-300">{server.id}</p>
            </div>
          ))}
        </div>
      </div>

      {/* TICKETS */}
      <div className="bg-neutral-900 p-6 rounded-xl border border-yellow-700">
        <h2 className="text-2xl mb-4">Ticket Conversations</h2>

        <div className="grid gap-4">
          {tickets.map((t) => (
            <div
              key={t.ticket_id}
              onClick={() => openTicket(t.ticket_id)}
              className="p-4 bg-neutral-800 rounded-lg border border-yellow-600 cursor-pointer hover:bg-neutral-700 transition"
            >
              <div className="flex justify-between">
                <p className="font-bold">#{t.ticket_id}</p>
                <span className="text-sm">{t.status}</span>
              </div>

              <p className="text-sm mt-2 text-yellow-300">
                {t.last_message}
              </p>

              <p className="text-xs mt-2">
                Messages: {t.count}
              </p>
            </div>
          ))}
        </div>
      </div>
    </div>
  );
}