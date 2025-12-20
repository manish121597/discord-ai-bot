"use client";

import { useEffect, useState } from "react";

export default function AdminLogs() {
  const [logs, setLogs] = useState([]);

  useEffect(() => {
    const token = localStorage.getItem("token");

    fetch("http://localhost:8081/admin_logs", {
      headers: {
        Authorization: `Bearer ${token}`,
      },
    })
      .then(res => res.json())
      .then(data => setLogs(data.logs || []));
  }, []);

  return (
    <div className="p-10 text-white max-w-5xl mx-auto">
      <h1 className="text-3xl text-yellow-400 mb-6">
        🧠 Admin Activity Logs
      </h1>

      {!logs.length && (
        <p className="text-gray-400">No admin activity yet.</p>
      )}

      {logs.map((log, i) => (
        <div
          key={i}
          className="bg-neutral-900 p-4 rounded mb-3 border border-neutral-800"
        >
          <div className="flex justify-between">
            <span className="font-semibold text-yellow-300">
              {log.action}
            </span>
            <span className="text-xs text-gray-400">
              {new Date(log.time).toLocaleString()}
            </span>
          </div>

          <div className="text-sm mt-1">
            Ticket ID: <b>{log.ticket_id}</b>
          </div>

          {log.message && (
            <div className="text-sm text-gray-300 mt-2">
              “{log.message}”
            </div>
          )}
        </div>
      ))}
    </div>
  );
}
