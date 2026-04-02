"use client";

import Link from "next/link";
import { motion } from "framer-motion";
import { ArrowRight, Sparkles, Zap, ShieldCheck, TimerReset } from "lucide-react";
import { useEffect, useState } from "react";
import { getOverview, getServers, getTickets } from "../lib/api";
import MetricCard from "../components/MetricCard";
import MiniBarChart from "../components/MiniBarChart";

export default function Dashboard() {
  const [servers, setServers] = useState([]);
  const [tickets, setTickets] = useState([]);
  const [overview, setOverview] = useState(null);
  const [loading, setLoading] = useState(true);

  useEffect(() => {
    async function load() {
      try {
        setLoading(true);
        const [overviewData, serverData, ticketData] = await Promise.all([
          getOverview(),
          getServers(),
          getTickets(),
        ]);
        setOverview(overviewData);
        setServers(serverData.servers || []);
        setTickets((ticketData.tickets || []).slice(0, 6));
      } catch (error) {
        console.error("Dashboard load error:", error);
      } finally {
        setLoading(false);
      }
    }

    load();
  }, []);

  const stats = overview?.stats || {};
  const intentChart = Object.entries(overview?.intent_breakdown || {}).map(([label, value]) => ({
    label,
    value,
  }));
  const activityChart = (overview?.activity || []).map((item) => ({
    label: item.label,
    value: item.value,
  }));

  return (
    <div>
      <section className="hero-grid">
        <motion.div
          className="hero-card"
          initial={{ opacity: 0, y: 16 }}
          animate={{ opacity: 1, y: 0 }}
          transition={{ duration: 0.4 }}
        >
          <p className="eyebrow">Overview</p>
          <h1>Support ops, without the clutter.</h1>
          <p className="hero-copy">
            Monitor ticket load, spot escalations, and jump into live conversations quickly.
          </p>
          <div className="hero-actions">
            <Link href="/tickets" className="primary-button">
              Review live tickets
            </Link>
            <Link href="/admin/logs" className="secondary-button">
              Open admin activity
            </Link>
          </div>
          <div className="hero-points">
            <span className="hero-pill">
              <Zap size={14} />
              Fast triage
            </span>
            <span className="hero-pill">
              <ShieldCheck size={14} />
              Human review
            </span>
            <span className="hero-pill">
              <TimerReset size={14} />
              Live updates
            </span>
          </div>
        </motion.div>

        <div className="panel">
          <div className="panel-header">
            <h3>Live health</h3>
            <Sparkles size={18} />
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
                <span>Open support load</span>
                <strong>{stats.tickets_open || 0}</strong>
              </div>
              <div className="bar-track">
                <div className="bar-fill" style={{ width: `${Math.min((stats.tickets_open || 0) * 12, 100)}%` }} />
              </div>
            </div>
            <div className="bar-row">
              <div className="bar-meta">
                <span>Escalated reviews</span>
                <strong>{stats.tickets_escalated || 0}</strong>
              </div>
              <div className="bar-track">
                <div className="bar-fill" style={{ width: `${Math.min((stats.tickets_escalated || 0) * 20, 100)}%` }} />
              </div>
            </div>
          </div>
        </div>
      </section>

      <section className="metrics-grid">
        <MetricCard
          label="Tickets"
          value={stats.tickets_total || 0}
          detail="Tracked conversations"
          accent="blue"
        />
        <MetricCard
          label="Open"
          value={stats.tickets_open || 0}
          detail="Need attention"
          accent="green"
        />
        <MetricCard
          label="Escalated"
          value={stats.tickets_escalated || 0}
          detail="Waiting for review"
          accent="purple"
        />
        <MetricCard
          label="Messages"
          value={stats.messages_total || 0}
          detail="Stored history"
          accent="orange"
        />
      </section>

      <section className="content-grid">
        <MiniBarChart
          title="Intent mix"
          items={intentChart}
          emptyLabel="Intent data will appear as soon as more tickets are processed."
        />

        <MiniBarChart
          title="Most active conversations"
          items={activityChart}
          emptyLabel="Activity insights will appear once live tickets are available."
        />
      </section>

      <section className="panel" style={{ marginTop: 18 }}>
        <div className="section-header">
          <div>
            <p className="eyebrow">Recent</p>
            <h3>Priority tickets</h3>
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
            {tickets.map((ticket) => (
              <Link key={ticket.ticket_id} href={`/tickets/${ticket.ticket_id}`} className="ticket-card">
                <div className="ticket-title-row">
                  <div>
                    <p className="eyebrow">{ticket.channel_name?.replace("ticket-", "").replace("-", " / ")}</p>
                    <h3>#{ticket.ticket_id}</h3>
                  </div>
                  <span className={`status-pill ${ticket.status}`}>{ticket.status}</span>
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
