"use client";

function getMessageText(message) {
  return message.content || message.text || "";
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

  return "";
}

export default function ConversationViewer({ messages, baseUrl }) {
  return (
    <div className="flex-1 overflow-y-auto p-4">
      {messages.length === 0 && (
        <p className="text-yellow-500">No messages yet</p>
      )}

      {messages.map((message, index) => {
        const author = message.author || message.role || "Unknown";
        const isAdmin = author === "ADMIN" || author === "assistant";

        return (
          <div
            key={index}
            className={`mb-4 flex ${isAdmin ? "justify-end" : "justify-start"}`}
          >
            <div
              className={`max-w-[70%] rounded-xl p-3 text-sm ${
                isAdmin
                  ? "bg-yellow-500 text-black"
                  : "bg-neutral-800 text-white"
              }`}
            >
              <div className="mb-1 text-xs opacity-60">
                {isAdmin ? "ADMIN" : author}
              </div>

              <div>{getMessageText(message) || "No text content"}</div>

              {Array.isArray(message.attachments) &&
                message.attachments.map((attachment, idx) => {
                  const url = getAttachmentUrl(baseUrl, attachment);

                  if (!url) {
                    return null;
                  }

                  return (
                    <a
                      key={idx}
                      href={url}
                      target="_blank"
                      rel="noreferrer"
                    >
                      <img
                        src={url}
                        alt={`Attachment ${idx + 1}`}
                        className="mt-2 max-h-60 rounded-lg border border-neutral-700"
                      />
                    </a>
                  );
                })}
            </div>
          </div>
        );
      })}
    </div>
  );
}
