"use client";

import Link from "next/link";
import { motion } from "framer-motion";
import {
  ArrowRight,
  BellRing,
  Bot,
  ShieldCheck,
  Sparkles,
  TimerReset,
  TriangleAlert,
  Zap,
} from "lucide-react";
import { useEffect, useMemo, useState } from "react";
import { getOverview, getServers, getTickets } from "../lib/api";
import { createRealtimeConnection } from "../lib/realtime";
import MetricCard from "../components/MetricCard";
import MiniBarChart from "../components/MiniBarChart";

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

function buildOverview(tickets) {
  const statusBreakdown = {};
  const intentBreakdown = {};
  const priorityBreakdown = {};
  const userMap = new Map();
  let attachmentsTotal = 0;

  for (const ticket of tickets) {
    statusBreakdown[ticket.status] = (statusBreakdown[ticket.status] || 0) + 1;
    intentBreakdown[ticket.intent || "query"] = (intentBreakdown[ticket.intent || "query"] || 0) + 1;
    priorityBreakdown[ticket.priority || "LOW"] = (priorityBreakdown[ticket.priority || "LOW"] || 0) + 1;
    attachmentsTotal += ticket.attachments_count || 0;
    userMap.set(ticket.user_name, (userMap.get(ticket.user_name) || 0) + (ticket.count || 0));
  }

  return {
    stats: {
      tickets_total: tickets.length,
      tickets_open: statusBreakdown.OPEN || 0,
      tickets_escalated: statusBreakdown.ESCALATED || 0,
      messages_total: tickets.reduce((sum, ticket) => sum + (ticket.count || 0), 0),
      attachments_total: attachmentsTotal,
      pending_tickets: tickets.filter((ticket) => ["OPEN", "ESCALATED", "PAUSED"].includes(ticket.status)).length,
      high_priority: priorityBreakdown.HIGH || 0,
    },
    intent_breakdown: intentBreakdown,
    priority_breakdown: priorityBreakdown,
    top_users: [...userMap.entries()]
      .sort((left, right) => right[1] - left[1])
      .slice(0, 5)
      .map(([label, value]) => ({ label, value })),
  };
}

export default function Dashboard() {
  const [servers, setServers] = useState([]);
  const [tickets, setTickets] = useState([]);
  const [overviewData, setOverviewData] = useState(null);
  const [loading, setLoading] = useState(true);
  const [connected, setConnected] = useState(false);

  useEffect(() => {
    async function load() {
      try {
        setLoading(true);
        const [serverData, ticketData, overview] = await Promise.all([getServers(), getTickets(), getOverview()]);
        setServers(serverData.servers || []);
        setTickets(ticketData.tickets || []);
        setOverviewData(overview || null);
      } catch (error) {
        console.error("Dashboard load error:", error);
      } finally {
        setLoading(false);
      }
    }

    load();
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
        if (event.event === "stats_updated") {
          setOverviewData(event.payload);
        }
      },
    });
    return () => connection.close();
  }, []);

  const overview = useMemo(() => buildOverview(tickets), [tickets]);
  const stats = overviewData?.stats || overview.stats;
  const intentChart = Object.entries(overviewData?.intent_breakdown || overview.intent_breakdown || {}).map(([label, value]) => ({
    label,
    value,
  }));
  const priorityChart = Object.entries(overviewData?.priority_breakdown || overview.priority_breakdown || {}).map(([label, value]) => ({
    label,
    value,
  }));
  const activeUsers = overviewData?.top_users || overview.top_users || [];
  const staffMetrics = overviewData?.staff_metrics || [];

  return (
    <div>
      <section className="hero-grid">
        <motion.div
          className="hero-card"
          initial={{ opacity: 0, y: 16 }}
          animate={{ opacity: 1, y: 0 }}
          transition={{ duration: 0.4 }}
        >
          <p className="eyebrow">Ops center</p>
          <h1>Faster triage, fewer manual checks, cleaner ticket control.</h1>
          <p className="hero-copy">
            This dashboard now runs like an internal control room: live ticket intake, AI-assisted handling,
            and high-priority review without waiting on page refreshes.
          </p>
          <div className="hero-actions">
            <Link href="/tickets" className="primary-button">
              Open live queue
            </Link>
            <Link href="/admin/logs" className="secondary-button">
              Review admin activity
            </Link>
          </div>
          <div className="hero-points">
            <span className="hero-pill">
              <Zap size={14} />
              Instant queue sync
            </span>
            <span className="hero-pill">
              <ShieldCheck size={14} />
              Staff controls
            </span>
            <span className="hero-pill">
              <TimerReset size={14} />
              Faster response flow
            </span>
          </div>
        </motion.div>

        <div className="panel">
          <div className="panel-header">
            <h3>Live health</h3>
            <span className={`pill live-pill ${connected ? "connected" : ""}`}>
              <BellRing size={14} />
              {connected ? "Connected" : "Connecting"}
            </span>
          </div>
          <div className="bar-list">
            <div className="bar-row">
              <div className="bar-meta">
                <span>Connected servers</span>
                <strong>{servers.length}</strong>
              </div>
              <div className="bar-track">
                <div className="bar-fill" style={{ width: `${Math.min(servers.length * 22, 100)}%` }} />
              </div>
            </div>
            <div className="bar-row">
              <div className="bar-meta">
                <span>Pending tickets</span>
                <strong>{stats.pending_tickets || 0}</strong>
              </div>
              <div className="bar-track">
                <div className="bar-fill" style={{ width: `${Math.min((stats.pending_tickets || 0) * 12, 100)}%` }} />
              </div>
            </div>
            <div className="bar-row">
              <div className="bar-meta">
                <span>High priority</span>
                <strong>{stats.high_priority || 0}</strong>
              </div>
              <div className="bar-track">
                <div className="bar-fill danger-fill" style={{ width: `${Math.min((stats.high_priority || 0) * 24, 100)}%` }} />
              </div>
            </div>
          </div>
        </div>
      </section>

      <section className="metrics-grid">
        <MetricCard label="Tickets" value={stats.tickets_total || 0} detail="Tracked conversations" accent="blue" />
        <MetricCard label="Pending" value={stats.pending_tickets || 0} detail="Need action" accent="green" />
        <MetricCard label="Escalated" value={stats.tickets_escalated || 0} detail="Need staff review" accent="purple" />
        <MetricCard label="Messages" value={stats.messages_total || 0} detail="Stored history" accent="orange" />
      </section>

      <section className="content-grid">
        <MiniBarChart
          title="Intent mix"
          items={intentChart}
          emptyLabel="Intent data will appear as soon as more tickets are processed."
        />

        <MiniBarChart
          title="Priority pressure"
          items={priorityChart}
          emptyLabel="Priority distribution will appear once tickets are classified."
        />
      </section>

      <section className="content-grid" style={{ marginTop: 18 }}>
        <MiniBarChart
          title="Top active users"
          items={activeUsers}
          emptyLabel="User activity will appear once tickets become active."
        />

        <div className="panel">
          <div className="panel-header">
            <h3>Watchlist</h3>
            <TriangleAlert size={18} />
          </div>
          <div className="bar-list">
            {(tickets || [])
              .filter((ticket) => ticket.priority === "HIGH" || ticket.overdue)
              .slice(0, 5)
              .map((ticket) => (
                <Link key={ticket.ticket_id} href={`/tickets/${ticket.ticket_id}`} className="watchlist-item">
                  <div>
                    <strong>#{ticket.ticket_id}</strong>
                    <p>{ticket.user_name}</p>
                  </div>
                  <span className="status-pill HIGH">{ticket.priority || "HIGH"}</span>
                </Link>
              ))}
            {!loading && !tickets.some((ticket) => ticket.priority === "HIGH" || ticket.overdue) ? (
              <p className="empty-state">No critical tickets right now.</p>
            ) : null}
          </div>
        </div>
      </section>

      <section className="content-grid" style={{ marginTop: 18 }}>
        <div className="panel">
          <div className="panel-header">
            <h3>Staff throughput</h3>
            <Bot size={18} />
          </div>
          {!staffMetrics.length ? (
            <p className="empty-state">Staff metrics will populate as admin actions are logged.</p>
          ) : (
            <div className="bar-list">
              {staffMetrics.slice(0, 5).map((item) => (
                <div key={item.label} className="watchlist-item">
                  <div>
                    <strong>{item.label}</strong>
                    <p>
                      {item.replies} replies · {item.closes} closes · {item.claims} claims
                    </p>
                  </div>
                  <span className="pill compact-pill">{item.value} total</span>
                </div>
              ))}
            </div>
          )}
        </div>

        <div className="panel">
          <div className="panel-header">
            <h3>Ops snapshot</h3>
            <Sparkles size={18} />
          </div>
          <div className="bar-list">
            <div className="bar-row">
              <div className="bar-meta">
                <span>Average first response</span>
                <strong>{stats.avg_response_minutes || 0} min</strong>
              </div>
              <div className="bar-track">
                <div className="bar-fill" style={{ width: `${Math.min((stats.avg_response_minutes || 0) * 8, 100)}%` }} />
              </div>
            </div>
            <div className="bar-row">
              <div className="bar-meta">
                <span>Stored attachments</span>
                <strong>{stats.attachments_total || 0}</strong>
              </div>
              <div className="bar-track">
                <div className="bar-fill" style={{ width: `${Math.min((stats.attachments_total || 0) * 8, 100)}%` }} />
              </div>
            </div>
            <div className="bar-row">
              <div className="bar-meta">
                <span>Open tickets</span>
                <strong>{stats.tickets_open || 0}</strong>
              </div>
              <div className="bar-track">
                <div className="bar-fill" style={{ width: `${Math.min((stats.tickets_open || 0) * 14, 100)}%` }} />
              </div>
            </div>
          </div>
        </div>
      </section>

      <section className="panel" style={{ marginTop: 18 }}>
        <div className="section-header">
          <div>
            <p className="eyebrow">Recent</p>
            <h3>Priority queue</h3>
          </div>
          <Link href="/tickets" className="secondary-button">
            <span>View all tickets</span>
            <ArrowRight size={16} />
          </Link>
        </div>

        {loading ? (
          <p className="empty-state">Loading overview...</p>
        ) : (
          <div className="ticket-grid" style={{ marginTop: 18 }}>
            {tickets.slice(0, 6).map((ticket) => (
              <Link key={ticket.ticket_id} href={`/tickets/${ticket.ticket_id}`} className="ticket-card">
                <div className="ticket-title-row">
                  <div>
                    <p className="eyebrow">{ticket.channel_name?.replace("ticket-", "").replace("-", " / ")}</p>
                    <h3>#{ticket.ticket_id}</h3>
                  </div>
                  <div className="inline-controls">
                    <span className={`status-pill ${ticket.priority || "LOW"}`}>{ticket.priority || "LOW"}</span>
                    <span className={`status-pill ${ticket.status}`}>{ticket.status}</span>
                  </div>
                </div>
                <p className="ticket-preview">{ticket.last_message || "No recent message yet."}</p>
                <div className="meta-row">
                  <span className="subtle-text">{ticket.user_name}</span>
                  <span className="pill compact-pill">{ticket.intent || "query"}</span>
                </div>
              </Link>
            ))}
          </div>
        )}
      </section>
    </div>
  );
}
