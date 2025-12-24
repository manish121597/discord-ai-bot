"use client";

import { useState, useEffect } from "react";
import { useRouter } from "next/navigation";

export default function Dashboard() {
  const router = useRouter();
  const [servers, setServers] = useState([]);
  const [tickets, setTickets] = useState([]);

  // 🔒 Redirect user to login page if NO token exists
  useEffect(() => {
    const token = localStorage.getItem("token");
    if (!token) router.push("/login");
  }, []);

  async function loadServers() {
    const token = localStorage.getItem("token");
  
    const res = await fetch("http://localhost:8081/server_map", {
      headers: {
        Authorization: `Bearer ${token}`,
      },
    });
  
    const data = await res.json();
    setServers(data.servers || []);
  }


  async function loadTickets() {
    const token = localStorage.getItem("token");

    const res = await fetch("http://localhost:8081/tickets", {
      headers: {
        Authorization: `Bearer ${token}`,
      },
    });

    const data = await res.json();
    setTickets(data.tickets || []);
  }

  return (
    <div className="min-h-screen bg-black text-yellow-400 p-10">
      <h1 className="text-4xl font-bold mb-10">
        ⚡ Donde Ticket Manager — Admin Dashboard
      </h1>

      {/* SERVER MAP */}
      <div className="bg-neutral-900 p-8 rounded-xl shadow-lg border border-yellow-700 mb-10">
        <h2 className="text-2xl mb-4">Server Map</h2>
        <button
          onClick={loadServers}
          className="bg-yellow-600 hover:bg-yellow-700 text-black px-4 py-2 rounded-lg"
        >
          Reload Servers
        </button>

        <pre className="text-yellow-200 mt-4 p-3 bg-neutral-800 rounded-lg max-h-60 overflow-auto">
          {JSON.stringify(servers, null, 2)}
        </pre>
      </div>

      {/* TICKET CONVERSATIONS */}
      <div className="bg-neutral-900 p-8 rounded-xl shadow-lg border border-yellow-700">
        <h2 className="text-2xl mb-4">Ticket Conversations</h2>

        <button
          onClick={loadTickets}
          className="bg-yellow-600 hover:bg-yellow-700 text-black px-4 py-2 rounded-lg"
        >
          Reload Tickets
        </button>

        <pre className="text-yellow-200 mt-4 p-3 bg-neutral-800 rounded-lg max-h-96 overflow-auto">
          {JSON.stringify(tickets, null, 2)}
        </pre>
      </div>
    </div>
  );
}
