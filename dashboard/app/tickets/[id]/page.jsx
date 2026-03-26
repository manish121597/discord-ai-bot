"use client";

import { useEffect, useRef, useState } from "react";
import { useRouter } from "next/navigation";
import ConversationViewer from "../../../components/ConversationViewer";
import {
  closeTicket,
  getApiBase,
  getConversation,
  sendReply,
} from "../../../lib/api";

export default function TicketDetail({ params }) {
  const { id } = params;
  const router = useRouter();
  const chatRef = useRef(null);

  const [messages, setMessages] = useState([]);
  const [reply, setReply] = useState("");
  const [loading, setLoading] = useState(true);
  const [sending, setSending] = useState(false);

  async function loadTicket() {
    try {
      const data = await getConversation(id);
      setMessages(data.messages || []);
    } catch (err) {
      console.error("Load error:", err);
    } finally {
      setLoading(false);
      setTimeout(() => {
        chatRef.current?.scrollTo({
          top: chatRef.current.scrollHeight,
          behavior: "smooth",
        });
      }, 100);
    }
  }

  useEffect(() => {
    loadTicket();
    const interval = setInterval(loadTicket, 4000);
    return () => clearInterval(interval);
  }, [id]);

  async function handleSendReply() {
    if (!reply.trim()) {
      return;
    }

    try {
      setSending(true);
      await sendReply(id, reply.trim());
      setReply("");
      await loadTicket();
    } catch (err) {
      console.error("Reply error:", err);
    } finally {
      setSending(false);
    }
  }

  function handleKeyDown(event) {
    if (event.key === "Enter" && !event.shiftKey) {
      event.preventDefault();
      handleSendReply();
    }
  }

  async function handleCloseTicket() {
    const confirmClose = window.confirm("Are you sure you want to close this ticket?");
    if (!confirmClose) {
      return;
    }

    try {
      await closeTicket(id);
      router.push("/tickets");
    } catch (err) {
      console.error("Close error:", err);
    }
  }

  if (loading) {
    return <div className="p-10 text-yellow-400">Loading chat...</div>;
  }

  return (
    <div className="flex min-h-screen flex-col bg-black text-white">
      <div className="flex items-center justify-between border-b border-neutral-800 p-4">
        <button
          type="button"
          onClick={() => router.push("/tickets")}
          className="text-yellow-400"
        >
          Back
        </button>

        <h1 className="font-bold text-yellow-400">Ticket #{id}</h1>

        <button
          type="button"
          onClick={handleCloseTicket}
          className="rounded bg-red-600 px-3 py-1 text-sm"
        >
          Close
        </button>
      </div>

      <div ref={chatRef} className="flex-1 overflow-y-auto">
        <ConversationViewer
          messages={messages}
          baseUrl={getApiBase()}
        />
      </div>

      <div className="border-t border-neutral-800 p-4">
        <textarea
          value={reply}
          onChange={(e) => setReply(e.target.value)}
          onKeyDown={handleKeyDown}
          placeholder="Type reply..."
          className="mb-3 w-full rounded bg-neutral-900 p-3 outline-none"
        />

        <button
          type="button"
          onClick={handleSendReply}
          disabled={sending}
          className="rounded bg-yellow-600 px-6 py-2 font-semibold text-black hover:bg-yellow-700"
        >
          {sending ? "Sending..." : "Send reply"}
        </button>
      </div>
    </div>
  );
}
