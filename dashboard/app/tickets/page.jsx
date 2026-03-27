"use client";

import Link from "next/link";
import { useEffect, useMemo, useState } from "react";
import { getTickets } from "../../lib/api";

export default function TicketsPage() {
  const [tickets, setTickets] = useState([]);
  const [loading, setLoading] = useState(true);
  const [search, setSearch] = useState("");
  const [statusFilter, setStatusFilter] = useState("ALL");

  useEffect(() => {
    async function loadTickets() {
      try {
        const data = await getTickets();
        setTickets(data.tickets || []);
      } catch (error) {
        console.error("Error loading tickets:", error);
      } finally {
        setLoading(false);
      }
    }

    loadTickets();
    const interval = setInterval(loadTickets, 5000);
    return () => clearInterval(interval);
  }, []);

  const filteredTickets = useMemo(() => {
    return tickets.filter((ticket) => {
      const searchMatch = [ticket.ticket_id, ticket.user_name, ticket.last_message, ticket.intent, ticket.category]
        .filter(Boolean)
        .join(" ")
        .toLowerCase()
        .includes(search.toLowerCase());

      const statusMatch = statusFilter === "ALL" || ticket.status === statusFilter;
      return searchMatch && statusMatch;
    });
  }, [search, statusFilter, tickets]);

  return (
    <div className="glass-card">
      <div className="section-header">
        <div>
          <p className="eyebrow">Live support operations</p>
          <h3>Ticket command center</h3>
        </div>
        <span className="pill">Auto-refresh every 5 seconds</span>
      </div>

      <div className="filter-row" style={{ marginTop: 18, marginBottom: 18 }}>
        <input
          className="search-input"
          placeholder="Search by ticket, user, intent, category, or recent message"
          value={search}
          onChange={(event) => setSearch(event.target.value)}
        />
        <select
          className="select-input"
          value={statusFilter}
          onChange={(event) => setStatusFilter(event.target.value)}
        >
          <option value="ALL">All statuses</option>
          <option value="OPEN">Open</option>
          <option value="ESCALATED">Escalated</option>
          <option value="PAUSED">Paused</option>
          <option value="CLOSED">Closed</option>
        </select>
      </div>

      {loading ? <p className="empty-state">Loading support tickets...</p> : null}

      {!loading && !filteredTickets.length ? (
        <p className="empty-state">No tickets matched that filter.</p>
      ) : (
        <div className="ticket-grid">
          {filteredTickets.map((ticket) => (
            <Link key={ticket.ticket_id} href={`/tickets/${ticket.ticket_id}`} className="ticket-card">
              <div className="ticket-title-row">
                <div>
                  <p className="eyebrow">{ticket.channel_name}</p>
                  <h3>#{ticket.ticket_id}</h3>
                </div>
                <span className={`status-pill ${ticket.status}`}>{ticket.status}</span>
              </div>

              <p className="ticket-preview">{ticket.last_message || "No conversation preview available."}</p>

              <div className="meta-row">
                <span className="pill">{ticket.intent || "query"}</span>
                <span className="pill">{ticket.category || "general"}</span>
              </div>

              <div className="meta-row" style={{ marginTop: 14 }}>
                <span className="subtle-text">{ticket.user_name}</span>
                <span className="subtle-text">
                  {ticket.count} msgs · {ticket.attachments_count} files
                </span>
              </div>
            </Link>
          ))}
        </div>
      )}
    </div>
  );
}
