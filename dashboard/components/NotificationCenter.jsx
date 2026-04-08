"use client";

import { ArrowRightLeft, Bell, TriangleAlert } from "lucide-react";
import { useEffect, useState } from "react";
import { getAlerts } from "../lib/api";
import { createRealtimeConnection } from "../lib/realtime";

function iconFor(kind) {
  if (kind === "handoff") {
    return <ArrowRightLeft size={16} />;
  }
  if (kind === "attention") {
    return <TriangleAlert size={16} />;
  }
  return <Bell size={16} />;
}

export default function NotificationCenter() {
  const [open, setOpen] = useState(false);
  const [alerts, setAlerts] = useState([]);

  useEffect(() => {
    getAlerts()
      .then((data) => setAlerts(data.alerts || []))
      .catch((error) => console.error("Failed to load alerts:", error));
  }, []);

  useEffect(() => {
    const connection = createRealtimeConnection({
      onEvent: (event) => {
        if (event.event === "alerts_updated") {
          setAlerts(event.payload.alerts || []);
        }
      },
    });
    return () => connection.close();
  }, []);

  return (
    <div className="notification-center">
      <button type="button" className="theme-toggle notification-trigger" onClick={() => setOpen((value) => !value)}>
        <Bell size={16} />
        <span>Alerts</span>
        {alerts.length ? <span className="notification-badge">{alerts.length}</span> : null}
      </button>

      {open ? (
        <div className="notification-panel">
          <div className="section-header slim-header">
            <strong>Recent alerts</strong>
          </div>
          {!alerts.length ? <p className="empty-state">No alerts yet.</p> : null}
          <div className="notes-list">
            {alerts.map((alert) => (
              <div key={alert.id} className={`note-card alert-card ${alert.priority || "LOW"}`}>
                <div className="note-meta">
                  <strong>
                    {iconFor(alert.kind)} {alert.title}
                  </strong>
                  <span>{new Date(alert.time).toLocaleString()}</span>
                </div>
                <p>{alert.body}</p>
              </div>
            ))}
          </div>
        </div>
      ) : null}
    </div>
  );
}
