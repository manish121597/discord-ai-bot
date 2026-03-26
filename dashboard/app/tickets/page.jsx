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
    } catch (err) {
      console.error("Error loading tickets:", err);
    } finally {
      setLoading(false);
    }
  }

  useEffect(() => {
    loadTickets();
    const interval = setInterval(loadTickets, 5000);
    return () => clearInterval(interval);
  }, []);

  useEffect(() => {
    const filteredList = tickets.filter((ticket) =>
      String(ticket.ticket_id).toLowerCase().includes(search.toLowerCase())
    );
    setFiltered(filteredList);
  }, [search, tickets]);

  function getStatusColor(status) {
    if (status === "OPEN") return "text-green-400";
    if (status === "CLOSED") return "text-red-400";
    return "text-yellow-400";
  }

  if (loading) {
    return <div className="p-10 text-yellow-400">Loading tickets...</div>;
  }

  return (
    <div className="min-h-screen bg-black p-10 text-yellow-400">
      <h1 className="mb-6 text-3xl">Live Support Tickets</h1>

      <input
        type="text"
        placeholder="Search ticket id..."
        value={search}
        onChange={(e) => setSearch(e.target.value)}
        className="mb-6 w-full rounded border border-yellow-600 bg-neutral-900 p-3 outline-none"
      />

      {!filtered.length && (
        <p className="text-yellow-500">No matching tickets.</p>
      )}

      <div className="grid gap-4">
        {filtered.map((ticket) => (
          <Link
            key={ticket.ticket_id}
            href={`/tickets/${ticket.ticket_id}`}
            className="block rounded-xl border border-yellow-700 bg-neutral-900 p-4 transition hover:bg-neutral-800"
          >
            <div className="flex items-center justify-between">
              <p className="font-bold">#{ticket.ticket_id}</p>
              <span className={getStatusColor(ticket.status)}>
                {ticket.status}
              </span>
            </div>

            <p className="mt-2 text-sm text-yellow-300">
              {ticket.last_message || "No messages yet"}
            </p>

            <p className="mt-2 text-xs">Messages: {ticket.count}</p>
          </Link>
        ))}
      </div>

      <p className="mt-6 text-xs text-yellow-600">
        Auto-refresh every 5 seconds
      </p>
    </div>
  );
}
