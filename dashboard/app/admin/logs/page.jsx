"use client";

import { useEffect, useState } from "react";
import { getAdminLogs } from "../../../lib/api";

export default function AdminLogs() {
  const [logs, setLogs] = useState([]);

  useEffect(() => {
    getAdminLogs()
      .then((data) => setLogs(data.logs || []))
      .catch((error) => console.error("Failed to load admin logs:", error));
  }, []);

  return (
    <div className="panel">
      <div className="section-header">
        <div>
          <p className="eyebrow">Audit trail</p>
          <h3>Admin activity logs</h3>
        </div>
        <span className="pill">{logs.length} entries</span>
      </div>

      {!logs.length ? (
        <p className="empty-state" style={{ marginTop: 18 }}>
          No admin activity yet.
        </p>
      ) : (
        <div className="bar-list" style={{ marginTop: 18 }}>
          {logs.map((log, index) => (
            <div key={index} className="ticket-card">
              <div className="ticket-title-row">
                <strong>{log.action}</strong>
                <span className="pill">{new Date(log.time).toLocaleString()}</span>
              </div>
              <p className="ticket-preview">
                Ticket #{log.ticket_id}
                {log.message ? ` · ${log.message}` : ""}
              </p>
              <div className="meta-row">
                <span className="subtle-text">Admin: {log.admin}</span>
              </div>
            </div>
          ))}
        </div>
      )}
    </div>
  );
}
