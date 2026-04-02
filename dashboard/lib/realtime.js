import { getApiBase } from "./api";

function getToken() {
  if (typeof window === "undefined") {
    return "";
  }
  return localStorage.getItem("token") || "";
}

export function createRealtimeConnection({ onEvent, onOpen, onClose }) {
  if (typeof window === "undefined") {
    return { close() {}, send() {} };
  }

  const token = getToken();
  const base = getApiBase().replace(/^http/, "ws");
  const socket = new WebSocket(`${base}/ws?token=${encodeURIComponent(token)}`);

  socket.addEventListener("open", () => {
    onOpen?.();
  });

  socket.addEventListener("close", () => {
    onClose?.();
  });

  socket.addEventListener("message", (event) => {
    try {
      const payload = JSON.parse(event.data);
      onEvent?.(payload);
    } catch (error) {
      console.error("Realtime payload parse error:", error);
    }
  });

  return {
    close() {
      socket.close();
    },
    send(data) {
      if (socket.readyState === WebSocket.OPEN) {
        socket.send(JSON.stringify(data));
      }
    },
  };
}
