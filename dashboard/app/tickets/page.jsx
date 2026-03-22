"use client";

import { useEffect, useState } from "react";
import Link from "next/link";
import { getTickets } from "../../lib/api";

export default function TicketsPage() {
  const [tickets, setTickets] = useState([]);
  const [loading, setLoading] = useState(true);

  async function loadTickets() {
    const data = await getTickets();
    setTickets(data.tickets || []);
    setLoading(false);
  }

  useEffect(() => {
    loadTickets();
    const interval = setInterval(loadTickets, 5000);
    return () => clearInterval(interval);
  }, []);

  if (loading) return <div className="p-10">Loading...</div>;

  return (
    <div className="p-10">
      <h1 className="text-3xl text-yellow-400 mb-6">
        📩 Live Support Tickets
      </h1>

      {!tickets.length && <p>No active tickets.</p>}

      {tickets.map((ticket) => (
        <Link
          key={ticket.ticket_id}
          href={`/tickets/${ticket.ticket_id}`}
          className="block bg-neutral-900 p-4 mb-3 rounded hover:bg-neutral-800"
        >
          <div className="flex justify-between">
            <span>Ticket #{ticket.ticket_id}</span>
            <span>{ticket.status}</span>
          </div>
          <div>{ticket.count} messages</div>
          <div>{ticket.last_message}</div>
        </Link>
      ))}
    </div>
  );
}