"use client";

import { useEffect, useState } from "react";
import Link from "next/link";

export default function TicketsPage() {
  const [tickets, setTickets] = useState([]);

  async function loadTickets() {
    const token = localStorage.getItem("token");

    const res = await fetch("http://localhost:8081/tickets", {
      headers: {
        Authorization: `Bearer ${token}`,
      },
    });

    const data = await res.json();
    setTickets(data.tickets || []);
  }

  // 🔁 AUTO REFRESH
  useEffect(() => {
    loadTickets();
    const interval = setInterval(loadTickets, 5000);
    return () => clearInterval(interval);
  }, []);

  return (
    <div className="p-10">
      <h1 className="text-3xl text-yellow-400 mb-6">
        📩 Live Support Tickets
      </h1>

      {!tickets.length && (
        <p className="text-gray-400">No active tickets.</p>
      )}

      {tickets.map((ticket) => (
        <Link
          key={ticket.ticket_id}
          href={`/tickets/${ticket.ticket_id}`}
          className="block bg-neutral-900 p-4 mb-3 rounded hover:bg-neutral-800"
        >
          <div className="flex justify-between items-center">
            <span className="font-semibold">
              Ticket #{ticket.ticket_id}
            </span>

            {/* ✅ STATUS BADGE */}
            <span
              className={`text-xs px-2 py-1 rounded ${
                ticket.status === "CLOSED"
                  ? "bg-red-700 text-white"
                  : "bg-green-700 text-white"
              }`}
            >
              {ticket.status}
            </span>
          </div>

          <div className="text-sm text-gray-400 mt-1">
            {ticket.count} messages
          </div>

          <div className="text-sm text-gray-400 mt-1 truncate">
            {ticket.last_message}
          </div>
        </Link>
      ))}
    </div>
  );
}
