"use client";

import Link from "next/link";
import { useDeferredValue, useEffect, useMemo, useState } from "react";
import { BellRing, CheckCheck, Radio, TriangleAlert } from "lucide-react";
import { bulkCloseTickets, getTickets } from "../../lib/api";
import { createRealtimeConnection } from "../../lib/realtime";

const PRIORITY_ORDER = { HIGH: 0, MEDIUM: 1, LOW: 2 };

function upsertTicket(list, incoming) {
  const next = [...list];
  const index = next.findIndex((item) => item.ticket_id === incoming.ticket_id);
  if (index === -1) {
    next.unshift(incoming);
  } else {
    next[index] = { ...next[index], ...incoming };
  }
  return next;
}

function SkeletonCard() {
  return (
    <div className="ticket-card skeleton-card">
      <div className="skeleton-line skeleton-title" />
      <div className="skeleton-line" />
      <div className="skeleton-line short" />
    </div>
  );
}

export default function TicketsPage() {
  const [tickets, setTickets] = useState([]);
  const [loading, setLoading] = useState(true);
  const [search, setSearch] = useState("");
  const [statusFilter, setStatusFilter] = useState("ALL");
  const [priorityFilter, setPriorityFilter] = useState("ALL");
  const [intentFilter, setIntentFilter] = useState("ALL");
  const [sortBy, setSortBy] = useState("newest");
  const [selected, setSelected] = useState([]);
  const [connected, setConnected] = useState(false);
  const [alerts, setAlerts] = useState([]);
  const deferredSearch = useDeferredValue(search);

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
  }, []);

  useEffect(() => {
    const connection = createRealtimeConnection({
      onOpen: () => setConnected(true),
      onClose: () => setConnected(false),
      onEvent: (event) => {
        if (["new_ticket", "ticket_updated"].includes(event.event)) {
          setTickets((current) => upsertTicket(current, event.payload));
        }

        if (event.event === "new_message") {
          setTickets((current) => upsertTicket(current, event.payload.ticket));
        }

        if (["new_ticket", "new_message"].includes(event.event)) {
          const ticket = event.payload.ticket || event.payload;
          if (!ticket?.ticket_id) {
            return;
          }

          setAlerts((current) => [
            {
              id: `${event.event}-${ticket.ticket_id}-${Date.now()}`,
              kind: ticket.priority === "HIGH" ? "critical" : "info",
              text:
                event.event === "new_ticket"
                  ? `New ticket #${ticket.ticket_id} entered the queue`
                  : `New activity on #${ticket.ticket_id}`,
            },
            ...current,
          ].slice(0, 4));
        }
      },
    });

    return () => connection.close();
  }, []);

  useEffect(() => {
    if (!alerts.length) {
      return undefined;
    }
    const timeout = setTimeout(() => {
      setAlerts((current) => current.slice(0, -1));
    }, 3600);
    return () => clearTimeout(timeout);
  }, [alerts]);

  const filteredTickets = useMemo(() => {
    const normalizedSearch = deferredSearch.trim().toLowerCase();
    const result = tickets.filter((ticket) => {
      const haystack = [
        ticket.ticket_id,
        ticket.user_name,
        ticket.last_message,
        ticket.intent,
        ticket.category,
        ...(ticket.tags || []),
      ]
        .filter(Boolean)
        .join(" ")
        .toLowerCase();

      const searchMatch = !normalizedSearch || haystack.includes(normalizedSearch);
      const statusMatch = statusFilter === "ALL" || ticket.status === statusFilter;
      const priorityMatch = priorityFilter === "ALL" || ticket.priority === priorityFilter;
      const intentMatch = intentFilter === "ALL" || ticket.intent === intentFilter;
      return searchMatch && statusMatch && priorityMatch && intentMatch;
    });

    result.sort((left, right) => {
      if (sortBy === "oldest") {
        return String(left.last_message_at || "").localeCompare(String(right.last_message_at || ""));
      }
      if (sortBy === "messages") {
        return (right.count || 0) - (left.count || 0);
      }
      if (sortBy === "priority") {
        return (PRIORITY_ORDER[left.priority] ?? 99) - (PRIORITY_ORDER[right.priority] ?? 99);
      }
      return String(right.last_message_at || "").localeCompare(String(left.last_message_at || ""));
    });
    return result;
  }, [deferredSearch, intentFilter, priorityFilter, sortBy, statusFilter, tickets]);

  async function handleBulkClose() {
    if (!selected.length) {
      return;
    }
    if (!window.confirm(`Close ${selected.length} selected tickets?`)) {
      return;
    }
    try {
      await bulkCloseTickets(selected);
      setTickets((current) =>
        current.map((ticket) =>
          selected.includes(ticket.ticket_id) ? { ...ticket, status: "CLOSED" } : ticket
        )
      );
      setSelected([]);
    } catch (error) {
      console.error("Bulk close failed:", error);
    }
  }

  function toggleTicket(ticketId) {
    setSelected((current) =>
      current.includes(ticketId) ? current.filter((item) => item !== ticketId) : [...current, ticketId]
    );
  }

  return (
    <div className="glass-card ops-page-card">
      <div className="section-header">
        <div>
          <p className="eyebrow">Tickets</p>
          <h3>Live queue</h3>
        </div>
        <div className="inline-controls">
          <span className={`pill live-pill ${connected ? "connected" : ""}`}>
            <Radio size={14} />
            {connected ? "Live" : "Reconnecting"}
          </span>
          <button type="button" className="secondary-button" onClick={handleBulkClose} disabled={!selected.length}>
            <CheckCheck size={16} />
            <span>Close selected</span>
          </button>
        </div>
      </div>

      {alerts.length ? (
        <div className="alert-stack">
          {alerts.map((alert) => (
            <div key={alert.id} className={`ops-alert ${alert.kind}`}>
              {alert.kind === "critical" ? <TriangleAlert size={16} /> : <BellRing size={16} />}
              <span>{alert.text}</span>
            </div>
          ))}
        </div>
      ) : null}

      <div className="filter-grid" style={{ marginTop: 18, marginBottom: 20 }}>
        <input
          className="search-input"
          placeholder="Search by ticket ID, user, message, tag, or intent"
          value={search}
          onChange={(event) => setSearch(event.target.value)}
        />
        <select className="select-input" value={statusFilter} onChange={(event) => setStatusFilter(event.target.value)}>
          <option value="ALL">All status</option>
          <option value="OPEN">Open</option>
          <option value="ESCALATED">Escalated</option>
          <option value="PAUSED">Paused</option>
          <option value="CLOSED">Closed</option>
        </select>
        <select
          className="select-input"
          value={priorityFilter}
          onChange={(event) => setPriorityFilter(event.target.value)}
        >
          <option value="ALL">All priority</option>
          <option value="HIGH">High</option>
          <option value="MEDIUM">Medium</option>
          <option value="LOW">Low</option>
        </select>
        <select className="select-input" value={intentFilter} onChange={(event) => setIntentFilter(event.target.value)}>
          <option value="ALL">All intent</option>
          <option value="query">Query</option>
          <option value="support">Payment / support</option>
          <option value="complaint">Problem</option>
          <option value="casual">Casual</option>
        </select>
        <select className="select-input" value={sortBy} onChange={(event) => setSortBy(event.target.value)}>
          <option value="newest">Newest</option>
          <option value="oldest">Oldest</option>
          <option value="messages">Most messages</option>
          <option value="priority">Highest priority</option>
        </select>
      </div>

      {loading ? (
        <div className="ticket-grid">
          <SkeletonCard />
          <SkeletonCard />
          <SkeletonCard />
          <SkeletonCard />
        </div>
      ) : null}

      {!loading && !filteredTickets.length ? (
        <p className="empty-state">No tickets matched that filter.</p>
      ) : null}

      {!loading && filteredTickets.length ? (
        <div className="ticket-grid">
          {filteredTickets.map((ticket) => (
            <div
              key={ticket.ticket_id}
              className={`ticket-card ops-ticket-card ${ticket.priority === "HIGH" || ticket.overdue ? "critical-ticket" : ""}`}
            >
              <div className="ticket-title-row">
                <label className="select-ticket">
                  <input
                    type="checkbox"
                    checked={selected.includes(ticket.ticket_id)}
                    onChange={() => toggleTicket(ticket.ticket_id)}
                  />
                  <div>
                    <p className="eyebrow">{ticket.channel_name}</p>
                    <h3>#{ticket.ticket_id}</h3>
                  </div>
                </label>
                <div className="inline-controls">
                  <span className={`status-pill ${ticket.priority || "LOW"}`}>{ticket.priority || "LOW"}</span>
                  <span className={`status-pill ${ticket.status}`}>{ticket.status}</span>
                </div>
              </div>

              <p className="ticket-preview">{ticket.last_message || "No conversation preview available."}</p>

              <div className="inline-controls">
                <span className="pill compact-pill">{ticket.intent || "query"}</span>
                <span className="pill compact-pill">{ticket.category || "general"}</span>
                {(ticket.tags || []).slice(0, 3).map((tag) => (
                  <span key={tag} className="pill compact-pill muted-pill">
                    {tag}
                  </span>
                ))}
              </div>

              <div className="meta-row ops-meta-row" style={{ marginTop: 14 }}>
                <div className="meta-stack">
                  <span className="subtle-text">{ticket.user_name}</span>
                  <span className="subtle-text">
                    {ticket.count} msgs · {ticket.attachments_count} files
                  </span>
                </div>
                <div className="meta-stack align-right">
                  <span className="subtle-text">{ticket.assigned_to ? `Claimed by ${ticket.assigned_to}` : "Unclaimed"}</span>
                  <Link href={`/tickets/${ticket.ticket_id}`} className="primary-button slim-button">
                    Open ticket
                  </Link>
                </div>
              </div>
            </div>
          ))}
        </div>
      ) : null}
    </div>
  );
}
