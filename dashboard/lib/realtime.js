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
  let socket = null;
  let reconnectTimer = null;
  let reconnectAttempt = 0;
  let manuallyClosed = false;

  function clearReconnectTimer() {
    if (reconnectTimer) {
      window.clearTimeout(reconnectTimer);
      reconnectTimer = null;
    }
  }

  function scheduleReconnect() {
    if (manuallyClosed || reconnectTimer) {
      return;
    }
    const delay = Math.min(1000 * Math.max(1, reconnectAttempt), 5000);
    reconnectTimer = window.setTimeout(() => {
      reconnectTimer = null;
      reconnectAttempt += 1;
      connect();
    }, delay);
  }

  function handleMessage(event) {
    try {
      const payload = JSON.parse(event.data);
      onEvent?.(payload);
    } catch (error) {
      console.error("Realtime payload parse error:", error);
    }
  }

  function connect() {
    clearReconnectTimer();
    socket = new WebSocket(`${base}/ws?token=${encodeURIComponent(token)}`);

    socket.addEventListener("open", () => {
      reconnectAttempt = 0;
      onOpen?.();
    });

    socket.addEventListener("close", () => {
      onClose?.();
      scheduleReconnect();
    });

    socket.addEventListener("error", () => {
      try {
        socket?.close();
      } catch (error) {
        console.error("Realtime socket close failed:", error);
      }
    });

    socket.addEventListener("message", handleMessage);
  }

  connect();

  return {
    close() {
      manuallyClosed = true;
      clearReconnectTimer();
      socket?.close();
    },
    send(data) {
      if (socket?.readyState === WebSocket.OPEN) {
        socket.send(JSON.stringify(data));
      }
    },
  };
}
