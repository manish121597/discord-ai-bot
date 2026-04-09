"use client";

import { ArrowRightLeft, Bell, TriangleAlert } from "lucide-react";
import { useEffect, useRef, useState } from "react";
import { getAlerts } from "../lib/api";
import { createRealtimeConnection } from "../lib/realtime";

const NOTIFICATION_PREF_KEY = "dashboard_notifications_enabled";

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
  const [browserEnabled, setBrowserEnabled] = useState(false);
  const [permission, setPermission] = useState("unsupported");
  const notifiedRef = useRef(new Set());

  useEffect(() => {
    if (typeof window === "undefined") {
      return;
    }

    setBrowserEnabled(localStorage.getItem(NOTIFICATION_PREF_KEY) === "true");
    if ("Notification" in window) {
      setPermission(Notification.permission);
    }
  }, []);

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

        if (["new_ticket", "new_message"].includes(event.event)) {
          const ticket = event.payload.ticket || event.payload;
          const dedupeId = `${event.event}-${ticket?.ticket_id}-${ticket?.last_message_at || ticket?.message?.timestamp || ""}`;
          if (!ticket?.ticket_id || notifiedRef.current.has(dedupeId)) {
            return;
          }
          notifiedRef.current.add(dedupeId);

          if (
            typeof window !== "undefined" &&
            browserEnabled &&
            "Notification" in window &&
            Notification.permission === "granted"
          ) {
            const body =
              ticket.last_message ||
              ticket.message?.text ||
              ticket.summary ||
              `Fresh activity on ticket #${ticket.ticket_id}`;

            if (document.hidden || !document.hasFocus()) {
              new Notification(
                event.event === "new_ticket" ? "New ticket" : `Ticket #${ticket.ticket_id} updated`,
                { body }
              );
            }

            if ("vibrate" in navigator) {
              navigator.vibrate([120, 40, 120]);
            }
          }
        }
      },
    });
    return () => connection.close();
  }, [browserEnabled]);

  async function toggleBrowserNotifications() {
    if (typeof window === "undefined") {
      return;
    }

    if (!browserEnabled) {
      if (!("Notification" in window)) {
        setPermission("unsupported");
        return;
      }
      const result = await Notification.requestPermission();
      setPermission(result);
      if (result !== "granted") {
        localStorage.setItem(NOTIFICATION_PREF_KEY, "false");
        setBrowserEnabled(false);
        return;
      }
      localStorage.setItem(NOTIFICATION_PREF_KEY, "true");
      setBrowserEnabled(true);
      return;
    }

    localStorage.setItem(NOTIFICATION_PREF_KEY, "false");
    setBrowserEnabled(false);
  }

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
          <div className="notification-settings">
            <button type="button" className="secondary-button slim-button" onClick={toggleBrowserNotifications}>
              {browserEnabled ? "Disable browser notifications" : "Enable browser notifications"}
            </button>
            <span className="subtle-text">
              {permission === "granted"
                ? "Browser alerts enabled"
                : permission === "denied"
                  ? "Browser notifications are blocked in this browser"
                  : permission === "unsupported"
                    ? "This browser does not support native notifications"
                    : "Enable this to get browser alerts while the dashboard is open"}
            </span>
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
