"use client";

export default function ConversationViewer({ messages, BASE }) {
  return (
    <div className="flex-1 p-4 overflow-y-auto">
      {messages.length === 0 && (
        <p className="text-yellow-500">
          No messages yet
        </p>
      )}

      {messages.map((m, i) => {
        const isAdmin = m.author === "ADMIN";

        return (
          <div
            key={i}
            className={flex mb-4 ${
              isAdmin ? "justify-end" : "justify-start"
            }}
          >
            <div
              className={max-w-[70%] p-3 rounded-xl text-sm ${
                isAdmin
                  ? "bg-yellow-500 text-black"
                  : "bg-neutral-800 text-white"
              }}
            >
              <div className="text-xs opacity-60 mb-1">
                {isAdmin ? "ADMIN" : m.author}
              </div>

              {m.content && <div>{m.content}</div>}

              {/* 📎 ATTACHMENTS */}
              {Array.isArray(m.attachments) &&
                m.attachments.map((img, idx) => (
                  <a
                    key={idx}
                    href={${BASE}/${img}}
                    target="_blank"
                    rel="noreferrer"
                  >
                    <img
                      src={${BASE}/${img}}
                      className="mt-2 rounded-lg max-h-60 border border-neutral-700 hover:scale-105 transition"
                    />
                  </a>
                ))}
            </div>
          </div>
        );
      })}
    </div>
  );
}