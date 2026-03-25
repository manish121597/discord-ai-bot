"use client";

import { useEffect, useState } from "react";

export default function TicketDetail({ params }) {
  const { id } = params;
  const [messages, setMessages] = useState([]);
  const [reply, setReply] = useState("");

  // 🔁 AUTO LOAD CHAT
  useEffect(() => {
    const token = localStorage.getItem("token");

    async function loadTicket() {
      const res = await fetch("http://localhost:8081/tickets", {
        headers: { Authorization: `Bearer ${token}` },
      });

      const data = await res.json();
      const ticket = data.tickets.find(t => t.ticket_id === id);
      setMessages(ticket?.messages || []);
    }

    loadTicket();
    const i = setInterval(loadTicket, 4000);
    return () => clearInterval(i);
  }, [id]);

  // 🚀 SEND ADMIN REPLY
  async function sendReply() {
    const token = localStorage.getItem("token");

    await fetch("http://localhost:8081/send_reply", {
      method: "POST",
      headers: {
        "Content-Type": "application/json",
        Authorization: `Bearer ${token}`,
      },
      body: JSON.stringify({ ticket_id: id, message: reply }),
    });

    setReply("");
  }

  // ❌ CLOSE TICKET
  async function closeTicket() {
    const token = localStorage.getItem("token");

    await fetch("http://localhost:8081/close_ticket", {
      method: "POST",
      headers: {
        "Content-Type": "application/json",
        Authorization: `Bearer ${token}`,
      },
      body: JSON.stringify({ ticket_id: id }),
    });

    alert("Ticket closed ❌");
    window.location.href = "/tickets";
  }

  return (
    <div className="max-w-4xl mx-auto p-6 text-white">
      <h1 className="text-2xl text-yellow-400 mb-6">
        🧾 Ticket #{id}
      </h1>

      {/* CHAT */}
      <div className="bg-neutral-900 p-4 rounded-lg h-[65vh] overflow-y-auto mb-4">
        {messages.map((m, i) => {
          const isAdmin = m.author === "ADMIN";

          return (
            <div
              key={i}
              className={`flex mb-4 ${isAdmin ? "justify-end" : "justify-start"}`}
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
                      href={`http://localhost:8081/${img}`}
                      target="_blank"
                      rel="noreferrer"
                    >
                      <img
                        src={`http://localhost:8081/${img}`}
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
