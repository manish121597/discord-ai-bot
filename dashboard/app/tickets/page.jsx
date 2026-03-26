"use client";

import { useEffect, useState } from "react";
import Link from "next/link";
import { getTickets } from "../../lib/api";

export default function TicketsPage() {
  const [tickets, setTickets] = useState([]);
  const [filtered, setFiltered] = useState([]);
  const [loading, setLoading] = useState(true);
  const [search, setSearch] = useState("");

  async function loadTickets() {
    try {
      const data = await getTickets();
      const list = data.tickets || [];
      setTickets(list);
      setFiltered(list);
      setLoading(false);
    } catch (err) {
      console.error("Error loading tickets:", err);
    }
  }

  useEffect(() => {
    loadTickets();
    const interval = setInterval(loadTickets, 5000);
    return () => clearInterval(interval);
  }, []);

  // 🔍 search filter
  useEffect(() => {
    const filteredList = tickets.filter((t) =>
      t.ticket_id.toLowerCase().includes(search.toLowerCase())
    );
    setFiltered(filteredList);
  }, [search, tickets]);

  function getStatusColor(status) {
    if (status === "OPEN") return "text-green-400";
    if (status === "CLOSED") return "text-red-400";
    return "text-yellow-400";
  }

  if (loading) {
    return (
      <div className="p-10 text-yellow-400">
        Loading tickets...
      </div>
    );
  }

  return (
    <div className="min-h-screen bg-black text-yellow-400 p-10">
      <h1 className="text-3xl mb-6">
        📩 Live Support Tickets
      </h1>

      {/* 🔍 Search */}
      <input
        type="text"
        placeholder="Search ticket id..."
        value={search}
        onChange={(e) => setSearch(e.target.value)}
        className="mb-6 w-full p-3 rounded bg-neutral-900 border border-yellow-600 outline-none"
      />

      {!filtered.length && (
        <p className="text-yellow-500">No matching tickets.</p>
      )}

      <div className="grid gap-4">
        {filtered.map((ticket) => (
          <Link
            key={ticket.ticket_id}
            href={/tickets/${ticket.ticket_id}}
            className="block p-4 bg-neutral-900 rounded-xl border border-yellow-700 hover:bg-neutral-800 transition"
          >
            <div className="flex justify-between items-center">
              <p className="font-bold">
                #{ticket.ticket_id}
              </p>
              <span className={getStatusColor(ticket.status)}>
                {ticket.status}
              </span>
            </div>

            <p className="text-sm mt-2 text-yellow-300">
              {ticket.last_message}
            </p>

            <p className="text-xs mt-2">
              Messages: {ticket.count}
            </p>
          </Link>
        ))}
      </div>

      {/* ⚡ Auto refresh indicator */}
      <p className="text-xs mt-6 text-yellow-600">
        Auto-refresh every 5 seconds
      </p>
    </div>
  );
}