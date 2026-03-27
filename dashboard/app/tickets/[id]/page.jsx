"use client";

import { useEffect, useRef, useState } from "react";
import { ArrowLeft, SendHorizontal, ShieldAlert } from "lucide-react";
import { useRouter } from "next/navigation";
import ConversationViewer from "../../../components/ConversationViewer";
import { closeTicket, getApiBase, getConversation, sendReply } from "../../../lib/api";

export default function TicketDetail({ params }) {
  const { id } = params;
  const router = useRouter();
  const chatRef = useRef(null);

  const [ticket, setTicket] = useState(null);
  const [messages, setMessages] = useState([]);
  const [reply, setReply] = useState("");
  const [loading, setLoading] = useState(true);
  const [sending, setSending] = useState(false);

  async function loadTicket() {
    try {
      const data = await getConversation(id);
      setTicket(data);
      setMessages(data.messages || []);
    } catch (error) {
      console.error("Load error:", error);
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
    } catch (error) {
      console.error("Reply error:", error);
    } finally {
      setSending(false);
    }
  }

  async function handleCloseTicket() {
    if (!window.confirm("Close this ticket and archive the thread on Discord?")) {
      return;
    }

    try {
      await closeTicket(id);
      router.push("/tickets");
    } catch (error) {
      console.error("Close error:", error);
    }
  }

  function handleKeyDown(event) {
    if (event.key === "Enter" && !event.shiftKey) {
      event.preventDefault();
      handleSendReply();
    }
  }

  if (loading) {
    return <div className="panel">Loading conversation...</div>;
  }

  return (
    <div className="two-column-grid">
      <section className="chat-shell">
        <div className="ticket-toolbar" style={{ marginBottom: 18 }}>
          <button type="button" className="secondary-button" onClick={() => router.push("/tickets")}>
            <ArrowLeft size={16} />
            <span>Back to tickets</span>
          </button>
          <span className={`status-pill ${ticket?.status}`}>{ticket?.status || "OPEN"}</span>
        </div>

        <div ref={chatRef} style={{ flex: 1 }}>
          <ConversationViewer messages={messages} baseUrl={getApiBase()} />
        </div>

        <div style={{ marginTop: 18 }}>
          <textarea
            value={reply}
            onChange={(event) => setReply(event.target.value)}
            onKeyDown={handleKeyDown}
            placeholder="Write a polished admin reply..."
            className="composer"
            rows={4}
          />
          <div className="inline-controls" style={{ marginTop: 12 }}>
            <button type="button" className="primary-button" onClick={handleSendReply} disabled={sending}>
              <SendHorizontal size={16} />
              <span>{sending ? "Sending..." : "Send reply"}</span>
            </button>
            <button type="button" className="secondary-button" onClick={handleCloseTicket}>
              Close ticket
            </button>
          </div>
        </div>
      </section>

      <aside className="panel">
        <div className="section-header">
          <div>
            <p className="eyebrow">Ticket intelligence</p>
            <h3>#{ticket?.ticket_id}</h3>
          </div>
          <ShieldAlert size={18} />
        </div>

        <div className="bar-list">
          <div>
            <p className="eyebrow">Detected intent</p>
            <strong>{ticket?.meta?.intent || "query"}</strong>
          </div>
          <div>
            <p className="eyebrow">Category</p>
            <strong>{ticket?.meta?.category || "general"}</strong>
          </div>
          <div>
            <p className="eyebrow">Stake username</p>
            <strong>{ticket?.meta?.username || "Not captured yet"}</strong>
          </div>
          <div>
            <p className="eyebrow">Files attached</p>
            <strong>{ticket?.meta?.attachments_total || 0}</strong>
          </div>
          <div>
            <p className="eyebrow">Customer</p>
            <strong>{ticket?.meta?.display_name || ticket?.meta?.user_name || "Unknown user"}</strong>
          </div>
        </div>
      </aside>
    </div>
  );
}
