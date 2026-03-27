"use client";

import Link from "next/link";
import { usePathname } from "next/navigation";
import {
  Activity,
  Bot,
  LayoutDashboard,
  LogOut,
  MessagesSquare,
  ShieldCheck,
} from "lucide-react";
import ThemeToggle from "./ThemeToggle";
import { logout } from "../lib/api";

const navItems = [
  { href: "/", label: "Overview", icon: LayoutDashboard },
  { href: "/tickets", label: "Tickets", icon: MessagesSquare },
  { href: "/admin/logs", label: "Activity", icon: Activity },
];

export default function AppShell({ children }) {
  const pathname = usePathname();

  if (pathname === "/login") {
    return children;
  }

  return (
    <div className="app-shell">
      <aside className="sidebar">
        <div className="brand-card">
          <div className="brand-mark">
            <Bot size={22} />
          </div>
          <div>
            <p className="eyebrow">Premium Support Stack</p>
            <h1>Donde AI Ops</h1>
          </div>
        </div>

        <nav className="sidebar-nav">
          {navItems.map((item) => {
            const Icon = item.icon;
            const active = pathname === item.href || pathname.startsWith(`${item.href}/`);
            return (
              <Link
                key={item.href}
                href={item.href}
                className={`nav-link ${active ? "active" : ""}`}
              >
                <Icon size={18} />
                <span>{item.label}</span>
              </Link>
            );
          })}
        </nav>

        <div className="sidebar-footer">
          <div className="trust-card">
            <ShieldCheck size={18} />
            <div>
              <strong>Admin secure zone</strong>
              <p>Live ticket operations and human-in-the-loop review.</p>
            </div>
          </div>

          <button type="button" className="ghost-button" onClick={logout}>
            <LogOut size={16} />
            <span>Logout</span>
          </button>
        </div>
      </aside>

      <main className="app-main">
        <header className="topbar">
          <div>
            <p className="eyebrow">Production-ready dashboard</p>
            <h2>AI support, ticket control, and live visibility in one place</h2>
          </div>
          <ThemeToggle />
        </header>
        <div className="page-container">{children}</div>
      </main>
    </div>
  );
}
