"use client";

import Link from "next/link";
import { motion } from "framer-motion";
import { ArrowRight, Sparkles } from "lucide-react";
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
          <p className="eyebrow">Sellable AI support product</p>
          <h1>Premium ticket intelligence for fast-moving Discord communities</h1>
          <p className="hero-copy">
            Your chatbot now has structured support logic, stored conversation memory, richer
            admin visibility, and a dashboard foundation that looks and feels like a serious SaaS
            product instead of an internal prototype.
          </p>
          <div className="hero-actions">
            <Link href="/tickets" className="primary-button">
              Review live tickets
            </Link>
            <Link href="/admin/logs" className="secondary-button">
              Open admin activity
            </Link>
          </div>
        </motion.div>

        <div className="panel">
          <div className="panel-header">
            <h3>System health</h3>
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
          label="Total tickets"
          value={stats.tickets_total || 0}
          detail="Every tracked support conversation across the Discord system."
          accent="blue"
        />
        <MetricCard
          label="Open tickets"
          value={stats.tickets_open || 0}
          detail="Active conversations still waiting for bot or admin resolution."
          accent="green"
        />
        <MetricCard
          label="Escalated"
          value={stats.tickets_escalated || 0}
          detail="Tickets currently paused for human review or payout verification."
          accent="purple"
        />
        <MetricCard
          label="Stored messages"
          value={stats.messages_total || 0}
          detail="Persisted chat history available for admin review and exports."
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
            <p className="eyebrow">Recent operations</p>
            <h3>Priority tickets</h3>
          </div>
          <Link href="/tickets" className="secondary-button">
            <span>View all tickets</span>
            <ArrowRight size={16} />
          </Link>
        </div>

        {loading ? (
          <p className="empty-state">Loading premium support view...</p>
        ) : (
          <div className="ticket-grid" style={{ marginTop: 18 }}>
            {tickets.map((ticket) => (
              <Link key={ticket.ticket_id} href={`/tickets/${ticket.ticket_id}`} className="ticket-card">
                <div className="ticket-title-row">
                  <div>
                    <p className="eyebrow">{ticket.channel_name}</p>
                    <h3>#{ticket.ticket_id}</h3>
                  </div>
                  <span className={`status-pill ${ticket.status}`}>{ticket.status}</span>
                </div>
                <p className="ticket-preview">{ticket.last_message || "No recent message yet."}</p>
                <div className="meta-row">
                  <span className="subtle-text">{ticket.user_name}</span>
                  <span className="subtle-text">{ticket.intent || "query"}</span>
                </div>
              </Link>
            ))}
          </div>
        )}
      </section>
    </div>
  );
}
