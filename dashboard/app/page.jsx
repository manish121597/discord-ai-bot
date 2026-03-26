"use client";

import { useEffect, useState } from "react";
import { useRouter } from "next/navigation";
import { getServers, getTickets } from "../lib/api";

export default function Dashboard() {
  const router = useRouter();
  const [servers, setServers] = useState([]);
  const [tickets, setTickets] = useState([]);
  const [loading, setLoading] = useState(true);

  useEffect(() => {
    const token = localStorage.getItem("token");
    if (!token) {
      router.push("/login");
      return;
    }

    loadAll();
  }, [router]);

  async function loadAll() {
    try {
      setLoading(true);
      const [serverData, ticketData] = await Promise.all([
        getServers(),
        getTickets(),
      ]);
      setServers(serverData.servers || []);
      setTickets(ticketData.tickets || []);
    } catch (err) {
      console.error("Dashboard load error:", err);
    } finally {
      setLoading(false);
    }
  }

  function openTicket(id) {
    router.push(`/tickets/${id}`);
  }

  return (
    <div className="min-h-screen bg-black p-10 text-yellow-400">
      <h1 className="mb-10 text-4xl font-bold">
        Donde Ticket Manager Admin Dashboard
      </h1>

      {loading && <p className="mb-6 text-yellow-500">Loading data...</p>}

      <div className="mb-10 rounded-xl border border-yellow-700 bg-neutral-900 p-6">
        <h2 className="mb-4 text-2xl">Server Map</h2>

        <div className="grid gap-4">
          {servers.map((server) => (
            <div
              key={server.id}
              className="rounded-lg border border-yellow-600 bg-neutral-800 p-4"
            >
              <p className="text-lg font-bold">{server.name}</p>
              <p className="text-sm text-yellow-300">{server.id}</p>
            </div>
          ))}

          {!loading && servers.length === 0 && (
            <p className="text-yellow-500">No servers found.</p>
          )}
        </div>
      </div>

      <div className="rounded-xl border border-yellow-700 bg-neutral-900 p-6">
        <h2 className="mb-4 text-2xl">Ticket Conversations</h2>

        <div className="grid gap-4">
          {tickets.map((ticket) => (
            <button
              key={ticket.ticket_id}
              type="button"
              onClick={() => openTicket(ticket.ticket_id)}
              className="rounded-lg border border-yellow-600 bg-neutral-800 p-4 text-left transition hover:bg-neutral-700"
            >
              <div className="flex justify-between">
                <p className="font-bold">#{ticket.ticket_id}</p>
                <span className="text-sm">{ticket.status}</span>
              </div>

              <p className="mt-2 text-sm text-yellow-300">
                {ticket.last_message || "No messages yet"}
              </p>

              <p className="mt-2 text-xs">Messages: {ticket.count}</p>
            </button>
          ))}

          {!loading && tickets.length === 0 && (
            <p className="text-yellow-500">No tickets found.</p>
          )}
        </div>
      </div>
    </div>
  );
}
