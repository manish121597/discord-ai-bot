"use client";

import { useEffect, useMemo, useRef, useState } from "react";
import {
  ArrowLeft,
  Bot,
  ClipboardPen,
  SendHorizontal,
  ShieldAlert,
  Sparkles,
  UserCheck,
} from "lucide-react";
import { useRouter } from "next/navigation";
import ConversationViewer from "../../../components/ConversationViewer";
import {
  addInternalNote,
  claimTicket,
  closeTicket,
  getApiBase,
  getConversation,
  getStoredUser,
  sendReply,
  suggestReply,
  updateTicketMeta,
} from "../../../lib/api";
import { createRealtimeConnection } from "../../../lib/realtime";

const QUICK_REPLIES = [
  "Payment is being checked right now.",
  "Please wait a moment while we review this.",
  "Please send the transaction ID so we can verify it.",
];

function upsertMessage(list, incoming) {
  const signature = `${incoming.timestamp || ""}-${incoming.author || ""}-${incoming.text || incoming.content || ""}`;
  if (list.some((item) => `${item.timestamp || ""}-${item.author || ""}-${item.text || item.content || ""}` === signature)) {
    return list;
  }
  return [...list, incoming];
}

export default function TicketDetail({ params }) {
  const { id } = params;
  const router = useRouter();
  const chatRef = useRef(null);
  const user = getStoredUser();

  const [ticket, setTicket] = useState(null);
  const [messages, setMessages] = useState([]);
  const [reply, setReply] = useState("");
  const [note, setNote] = useState("");
  const [loading, setLoading] = useState(true);
  const [sending, setSending] = useState(false);
  const [aiLoading, setAiLoading] = useState(false);
  const [typingUsers, setTypingUsers] = useState([]);
  const [liveState, setLiveState] = useState("connecting");
  const connectionRef = useRef(null);

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
  }, [id]);

  const composerLocked = useMemo(() => {
    const assigned = ticket?.meta?.assigned_to;
    return assigned && assigned !== user?.name;
  }, [ticket?.meta?.assigned_to, user?.name]);

  async function handleSendReply() {
    if (!reply.trim() || composerLocked) {
      return;
    }

    try {
      setSending(true);
      await sendReply(id, reply.trim());
      setReply("");
    } catch (error) {
      console.error("Reply error:", error);
      alert(error.message || "Reply failed");
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

  async function handleClaim() {
    try {
      const data = await claimTicket(id);
      setTicket((current) => ({
        ...(current || {}),
        meta: {
          ...(current?.meta || {}),
          assigned_to: data.assigned_to,
        },
      }));
    } catch (error) {
      console.error("Claim error:", error);
    }
  }

  async function handleSuggestReply() {
    try {
      setAiLoading(true);
      const suggestion = await suggestReply(id);
      setReply(suggestion.reply_text || "");
      setTicket((current) => ({
        ...(current || {}),
        meta: {
          ...(current?.meta || {}),
          intent: suggestion.intent,
          category: suggestion.category,
          priority: suggestion.priority,
          sentiment: suggestion.sentiment,
          tags: suggestion.tags,
        },
      }));
    } catch (error) {
      console.error("AI suggestion failed:", error);
    } finally {
      setAiLoading(false);
    }
  }

  async function handleNoteSave() {
    if (!note.trim()) {
      return;
    }
    try {
      const data = await addInternalNote(id, note.trim());
      setTicket((current) => ({
        ...(current || {}),
        meta: {
          ...(current?.meta || {}),
          internal_notes: data.notes,
        },
      }));
      setNote("");
    } catch (error) {
      console.error("Note save failed:", error);
    }
  }

  async function handleAutoReplyToggle() {
    try {
      const nextValue = !ticket?.meta?.auto_reply_enabled;
      await updateTicketMeta(id, { auto_reply_enabled: nextValue });
      setTicket((current) => ({
        ...(current || {}),
        meta: {
          ...(current?.meta || {}),
          auto_reply_enabled: nextValue,
        },
      }));
    } catch (error) {
      console.error("Auto reply toggle failed:", error);
    }
  }

  function handleKeyDown(event) {
    if (event.key === "Enter" && !event.shiftKey) {
      event.preventDefault();
      handleSendReply();
    }
  }

  useEffect(() => {
    const connection = createRealtimeConnection({
      onOpen: () => setLiveState("live"),
      onClose: () => setLiveState("reconnecting"),
      onEvent: (event) => {
        if (event.event === "ticket_updated" && event.payload.ticket_id === id) {
          setTicket((current) => ({
            ...(current || {}),
            ticket_id: id,
            status: event.payload.status,
            meta: {
              ...(current?.meta || {}),
              ...event.payload,
            },
          }));
        }
        if (event.event === "new_message" && event.payload.ticket_id === id) {
          setMessages((current) => upsertMessage(current, event.payload.message));
          if (event.payload.ticket) {
            setTicket((current) => ({
              ...(current || {}),
              ticket_id: id,
              status: event.payload.ticket.status,
              meta: {
                ...(current?.meta || {}),
                ...event.payload.ticket,
              },
            }));
          }
        }
        if (event.event === "typing" && event.payload.ticket_id === id && event.payload.user !== user?.name) {
          setTypingUsers([event.payload.user]);
          setTimeout(() => setTypingUsers([]), 1800);
        }
      },
    });
    connectionRef.current = connection;
    return () => connection.close();
  }, [id, user?.name]);

  function emitTyping() {
    connectionRef.current?.send({
      type: "typing",
      ticket_id: id,
      user: user?.name || "admin",
    });
  }

  if (loading) {
    return <div className="panel">Loading conversation...</div>;
  }

  return (
    <div className="two-column-grid ops-detail-grid">
      <section className="chat-shell">
        <div className="ticket-toolbar" style={{ marginBottom: 18 }}>
          <button type="button" className="secondary-button" onClick={() => router.push("/tickets")}>
            <ArrowLeft size={16} />
            <span>Back to tickets</span>
          </button>
          <div className="inline-controls">
            <span className={`pill live-pill ${liveState === "live" ? "connected" : ""}`}>
              {liveState === "live" ? "Live sync" : "Connecting"}
            </span>
            <span className={`status-pill ${ticket?.status}`}>{ticket?.status || "OPEN"}</span>
          </div>
        </div>

        <div className="detail-summary-strip">
          <span className="pill compact-pill">{ticket?.meta?.intent || "query"}</span>
          <span className="pill compact-pill">{ticket?.meta?.category || "general"}</span>
          <span className={`status-pill ${ticket?.meta?.priority || "LOW"}`}>{ticket?.meta?.priority || "LOW"}</span>
          <span className="subtle-text">{messages.length} messages</span>
        </div>

        <div ref={chatRef} style={{ flex: 1 }}>
          <ConversationViewer messages={messages} baseUrl={getApiBase()} />
        </div>

        {typingUsers.length ? (
          <div className="typing-indicator">
            <Bot size={14} />
            <span>{typingUsers.join(", ")} typing...</span>
          </div>
        ) : null}

        <div className="quick-reply-row">
          {QUICK_REPLIES.map((item) => (
            <button key={item} type="button" className="pill compact-pill muted-pill" onClick={() => setReply(item)}>
              {item}
            </button>
          ))}
        </div>

        <div style={{ marginTop: 18 }}>
          <textarea
            value={reply}
            onChange={(event) => {
              setReply(event.target.value);
              emitTyping();
            }}
            onKeyDown={handleKeyDown}
            placeholder={composerLocked ? `Claimed by ${ticket?.meta?.assigned_to}` : "Write a polished admin reply..."}
            className="composer"
            rows={5}
            disabled={composerLocked}
          />
          <div className="inline-controls" style={{ marginTop: 12 }}>
            <button type="button" className="primary-button" onClick={handleSendReply} disabled={sending || composerLocked}>
              <SendHorizontal size={16} />
              <span>{sending ? "Sending..." : "Send reply"}</span>
            </button>
            <button type="button" className="secondary-button" onClick={handleSuggestReply} disabled={aiLoading}>
              <Sparkles size={16} />
              <span>{aiLoading ? "Drafting..." : "Suggest reply"}</span>
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
            <p className="eyebrow">Ticket details</p>
            <h3>#{ticket?.ticket_id}</h3>
          </div>
          <ShieldAlert size={18} />
        </div>

        <div className="detail-stats-grid">
          <div className="detail-stat-card">
            <p className="eyebrow">Customer</p>
            <strong>{ticket?.meta?.display_name || ticket?.meta?.user_name || "Unknown user"}</strong>
          </div>
          <div className="detail-stat-card">
            <p className="eyebrow">Stake username</p>
            <strong>{ticket?.meta?.username || "Not captured"}</strong>
          </div>
          <div className="detail-stat-card">
            <p className="eyebrow">Files</p>
            <strong>{ticket?.meta?.attachments_total || 0}</strong>
          </div>
          <div className="detail-stat-card">
            <p className="eyebrow">Assigned</p>
            <strong>{ticket?.meta?.assigned_to || "Unclaimed"}</strong>
          </div>
        </div>

        <div className="ops-side-block">
          <div className="section-header slim-header">
            <strong>Ops controls</strong>
          </div>
          <div className="inline-controls">
            <button type="button" className="secondary-button" onClick={handleClaim}>
              <UserCheck size={16} />
              <span>Claim ticket</span>
            </button>
            <button type="button" className="secondary-button" onClick={handleAutoReplyToggle}>
              <Bot size={16} />
              <span>{ticket?.meta?.auto_reply_enabled !== false ? "Auto reply on" : "Auto reply off"}</span>
            </button>
          </div>
        </div>

        <div className="ops-side-block">
          <div className="section-header slim-header">
            <strong>Internal notes</strong>
            <ClipboardPen size={16} />
          </div>
          <textarea
            value={note}
            onChange={(event) => setNote(event.target.value)}
            className="composer compact-composer"
            rows={3}
            placeholder="Leave a private note for staff..."
          />
          <button type="button" className="secondary-button" style={{ marginTop: 10 }} onClick={handleNoteSave}>
            Save note
          </button>
          <div className="notes-list">
            {(ticket?.meta?.internal_notes || []).map((item, index) => (
              <div key={`${item.time}-${index}`} className="note-card">
                <div className="note-meta">
                  <strong>{item.author}</strong>
                  <span>{new Date(item.time).toLocaleString()}</span>
                </div>
                <p>{item.text}</p>
              </div>
            ))}
          </div>
        </div>
      </aside>
    </div>
  );
}
