"use client";

import { Bot, LockKeyhole, ShieldCheck } from "lucide-react";
import { useState } from "react";
import { useRouter } from "next/navigation";
import { login } from "../../lib/api";

export default function Login() {
  const router = useRouter();
  const [user, setUser] = useState("");
  const [pass, setPass] = useState("");
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState("");

  async function doLogin(event) {
    event.preventDefault();
    try {
      setLoading(true);
      setError("");
      const data = await login(user, pass);
      if (data.access_token) {
        router.push("/");
        return;
      }
      setError("Login failed. Please check your credentials.");
    } catch (err) {
      setError("Unable to reach the login service right now.");
    } finally {
      setLoading(false);
    }
  }

  return (
    <div className="login-page">
      <div className="login-card">
        <p className="eyebrow">AI support platform</p>
        <div className="brand-mark">
          <Bot size={24} />
        </div>
        <h1 className="login-title">Welcome back to Donde AI Ops</h1>
        <p className="muted-block">
          Monitor premium support conversations, intervene in live tickets, and keep the human
          escalation pipeline under control from one polished dashboard.
        </p>

        <div className="inline-controls" style={{ marginTop: 18 }}>
          <span className="pill">
            <ShieldCheck size={15} />
            Admin role access
          </span>
          <span className="pill">
            <LockKeyhole size={15} />
            JWT-protected session
          </span>
        </div>

        <form className="login-form" onSubmit={doLogin}>
          <input
            className="login-input"
            placeholder="Admin username"
            value={user}
            onChange={(event) => setUser(event.target.value)}
          />
          <input
            className="login-input"
            type="password"
            placeholder="Password"
            value={pass}
            onChange={(event) => setPass(event.target.value)}
          />
          {error ? <p className="empty-state">{error}</p> : null}
          <button className="primary-button" type="submit" disabled={loading}>
            {loading ? "Signing in..." : "Enter dashboard"}
          </button>
        </form>
      </div>
    </div>
  );
}
