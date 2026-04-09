"use client";

function getMessageText(message) {
  return message.text || message.content || "";
}

function getAttachmentUrl(base, attachment) {
  if (!attachment) {
    return "";
  }

  if (typeof attachment === "string") {
    return attachment.startsWith("http") ? attachment : `${base}/${attachment}`;
  }

  if (attachment.url) {
    return attachment.url.startsWith("http")
      ? attachment.url
      : `${base}${attachment.url.startsWith("/") ? "" : "/"}${attachment.url}`;
  }

  if (attachment.proxy_url) {
    return attachment.proxy_url;
  }

  if (attachment.local_url) {
    return attachment.local_url.startsWith("http")
      ? attachment.local_url
      : `${base}${attachment.local_url.startsWith("/") ? "" : "/"}${attachment.local_url}`;
  }

  return "";
}

function isImageAttachment(attachment) {
  const contentType = attachment?.content_type || "";
  const filename = attachment?.filename || "";
  return contentType.startsWith("image/") || /\.(png|jpe?g|gif|webp|bmp|svg)$/i.test(filename);
}

export default function ConversationViewer({ messages, baseUrl }) {
  return (
    <div className="conversation-scroll">
      {messages.length === 0 ? <p className="empty-state">No messages yet</p> : null}

      {messages.map((message, index) => {
        const author = message.author || message.role || "Unknown";
        const adminLike = ["ADMIN", "assistant", "X-Boty"].includes(author) || message.role === "assistant";

        return (
          <div key={index} className={`message-row ${adminLike ? "admin" : ""}`}>
            <div className="message-bubble">
              <div className="message-author">
                {adminLike ? author : `${author} · ${message.intent || "user"}`}
              </div>
              <div className="message-text">{getMessageText(message) || "No text content"}</div>

              {Array.isArray(message.attachments) && message.attachments.length > 0 ? (
                <div className="attachment-grid">
                  {message.attachments.map((attachment, attachmentIndex) => {
                    const url = getAttachmentUrl(baseUrl, attachment);
                    if (!url) {
                      return null;
                    }
                    return (
                      <a key={attachmentIndex} href={url} target="_blank" rel="noreferrer" className="attachment-card">
                        {isImageAttachment(attachment) ? (
                          <img
                            src={url}
                            alt={attachment.filename || `Attachment ${attachmentIndex + 1}`}
                            className="attachment-image"
                          />
                        ) : null}
                        <span className="attachment-label">
                          {attachment.filename || `Attachment ${attachmentIndex + 1}`}
                        </span>
                      </a>
                    );
                  })}
                </div>
              ) : null}

              {message.timestamp ? (
                <div className="message-time" style={{ marginTop: 10 }}>
                  {new Date(message.timestamp).toLocaleString()}
                </div>
              ) : null}
            </div>
          </div>
        );
      })}
    </div>
  );
}
