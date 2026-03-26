"use client";

import { useEffect, useState, useRef } from "react";
import { useRouter } from "next/navigation";
import ConversationViewer from "../../../components/ConversationViewer";

const BASE = "https://discord-ai-bot-1-p5hk.onrender.com";

export default function TicketDetail({ params }) {
  const { id } = params;
  const router = useRouter();

  const [messages, setMessages] = useState([]);
  const [reply, setReply] = useState("");
  const [loading, setLoading] = useState(true);
  const [sending, setSending] = useState(false);

  const chatRef = useRef(null);

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

      setTimeout(() => {
        chatRef.current?.scrollTo({
          top: chatRef.current.scrollHeight,
          behavior: "smooth",
        });
      }, 100);
    } catch (err) {
      console.error("Load error:", err);
    }
  }

  useEffect(() => {
    loadTicket();
    const i = setInterval(loadTicket, 4000);
    return () => clearInterval(i);
  }, [id]);

  async function sendReply() {
    if (!reply.trim()) return;

    try {
      setSending(true);

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
      await loadTicket();
    } catch (err) {
      console.error("Reply error:", err);
    } finally {
      setSending(false);
    }
  }

  function handleKey(e) {
    if (e.key === "Enter" && !e.shiftKey) {
      e.preventDefault();
      sendReply();
    }
  }

  async function closeTicket() {
    const confirmClose = confirm("Are you sure to close?");
    if (!confirmClose) return;

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

      router.push("/tickets");
    } catch (err) {
      console.error("Close error:", err);
    }
  }

  if (loading) {
    return (
      <div className="p-10 text-yellow-400">
        Loading chat...
      </div>
    );
  }

  return (
    <div className="min-h-screen bg-black text-white flex flex-col">
      
      {/* HEADER */}
      <div className="p-4 border-b border-neutral-800 flex justify-between items-center">
        <button
          onClick={() => router.push("/tickets")}
          className="text-yellow-400"
        >
          ← Back
        </button>

        <h1 className="text-yellow-400 font-bold">
          Ticket #{id}
        </h1>

        <button
          onClick={closeTicket}
          className="bg-red-600 px-3 py-1 rounded text-sm"
        >
          Close ❌
        </button>
      </div>

      {/* CHAT (COMPONENT USE) */}
      <div ref={chatRef} className="flex-1 overflow-y-auto">
        <ConversationViewer messages={messages} BASE={BASE} />
      </div>

      {/* INPUT */}
      <div className="p-4 border-t border-neutral-800">
        <textarea
          value={reply}
          onChange={(e) => setReply(e.target.value)}
          onKeyDown={handleKey}
          placeholder="Type reply..."
          className="w-full p-3 rounded bg-neutral-900 mb-3 outline-none"
        />

        <button
          onClick={sendReply}
          disabled={sending}
          className="bg-yellow-600 hover:bg-yellow-700 px-6 py-2 rounded text-black font-semibold"
        >
          {sending ? "Sending..." : "Send 🚀"}
        </button>
      </div>
    </div>
  );
}