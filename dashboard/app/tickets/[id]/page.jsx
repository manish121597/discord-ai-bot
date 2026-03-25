"use client";

import { useEffect, useState } from "react";

const BASE = "https://discord-ai-bot-1-p5hk.onrender.com";

export default function TicketDetail({ params }) {
  const { id } = params;
  const [messages, setMessages] = useState([]);
  const [reply, setReply] = useState("");
  const [loading, setLoading] = useState(true);

  // 🔁 LOAD CHAT
  async function loadTicket() {
    try {
      const token = localStorage.getItem("token");

      const res = await fetch(`${BASE}/api/tickets`, {
        headers: {
          Authorization: `Bearer ${token}`,
        },
      });

      const data = await res.json();

      const ticket = data.tickets?.find(
        (t) => String(t.ticket_id) === String(id)
      );

      setMessages(ticket?.messages || []);
      setLoading(false);
    } catch (err) {
      console.error("Load error:", err);
    }
  }

  // AUTO REFRESH
  useEffect(() => {
    loadTicket();
    const i = setInterval(loadTicket, 4000);
    return () => clearInterval(i);
  }, [id]);

  // 🚀 SEND REPLY
  async function sendReply() {
    if (!reply.trim()) return;

    try {
      const token = localStorage.getItem("token");

      await fetch(`${BASE}/api/send_reply`, {
        method: "POST",
        headers: {
          "Content-Type": "application/json",
          Authorization: `Bearer ${token}`,
        },
        body: JSON.stringify({
          ticket_id: id,
          message: reply,
        }),
      });

      setReply("");
      loadTicket(); // instant refresh
    } catch (err) {
      console.error("Reply error:", err);
    }
  }

  // ❌ CLOSE TICKET
  async function closeTicket() {
    try {
      const token = localStorage.getItem("token");

      await fetch(`${BASE}/api/close_ticket`, {
        method: "POST",
        headers: {
          "Content-Type": "application/json",
          Authorization: `Bearer ${token}`,
        },
        body: JSON.stringify({ ticket_id: id }),
      });

      alert("Ticket closed ❌");
      window.location.href = "/tickets";
    } catch (err) {
      console.error("Close error:", err);
    }
  }

  if (loading) {
    return <div className="p-10 text-white">Loading chat...</div>;
  }

  return (
    <div className="max-w-4xl mx-auto p-6 text-white">
      <h1 className="text-2xl text-yellow-400 mb-6">
        🧾 Ticket #{id}
      </h1>

      {/* CHAT */}
      <div className="bg-neutral-900 p-4 rounded-lg h-[65vh] overflow-y-auto mb-4">
        {messages.length === 0 && <p>No messages yet</p>}

        {messages.map((m, i) => {
          const isAdmin = m.author === "ADMIN";

          return (
            <div
              key={i}
              className={`flex mb-4 ${
                isAdmin ? "justify-end" : "justify-start"
              }`}
            >
              <div
                className={`max-w-[70%] p-3 rounded-lg text-sm ${
                  isAdmin
                    ? "bg-yellow-500 text-black"
                    : "bg-neutral-800 text-white"
                }`}
              >
                <div className="text-xs opacity-70 mb-1">
                  {isAdmin ? "ADMIN" : m.author}
                </div>

                {m.content && <div>{m.content}</div>}

                {/* 🖼️ ATTACHMENTS */}
                {Array.isArray(m.attachments) &&
                  m.attachments.map((img, idx) => (
                    <a
                      key={idx}
                      href={`${BASE}/${img}`}
                      target="_blank"
                      rel="noreferrer"
                    >
                      <img
                        src={`${BASE}/${img}`}
                        className="mt-2 rounded-lg max-h-60 border border-neutral-700"
                      />
                    </a>
                  ))}
              </div>
            </div>
          );
        })}
      </div>

      {/* REPLY */}
      <textarea
        value={reply}
        onChange={(e) => setReply(e.target.value)}
        placeholder="Type admin reply..."
        className="w-full p-3 rounded bg-neutral-800 text-white mb-3"
      />

      <button
        onClick={sendReply}
        className="bg-yellow-600 hover:bg-yellow-700 px-6 py-2 rounded text-black font-semibold"
      >
        Send Reply 🚀
      </button>

      {/* ❌ CLOSE */}
      <button
        onClick={closeTicket}
        className="mt-4 bg-red-600 hover:bg-red-700 px-6 py-2 rounded text-white font-semibold"
      >
        Close Ticket ❌
      </button>
    </div>
  );
}