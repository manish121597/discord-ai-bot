"use client";

import Link from "next/link";
import { usePathname } from "next/navigation";
import {
  Activity,
  Bot,
  LayoutDashboard,
  Menu,
  LogOut,
  MessagesSquare,
  X,
  ShieldCheck,
} from "lucide-react";
import { useState } from "react";
import ThemeToggle from "./ThemeToggle";
import { logout } from "../lib/api";

const navItems = [
  { href: "/", label: "Overview", icon: LayoutDashboard },
  { href: "/tickets", label: "Tickets", icon: MessagesSquare },
  { href: "/admin/logs", label: "Activity", icon: Activity },
];

export default function AppShell({ children }) {
  const pathname = usePathname();
  const [open, setOpen] = useState(false);

  if (pathname === "/login") {
    return children;
  }

  return (
    <div className="app-shell">
      <button type="button" className="mobile-menu-button" onClick={() => setOpen(true)}>
        <Menu size={18} />
        <span>Menu</span>
      </button>

      {open ? <div className="sidebar-overlay" onClick={() => setOpen(false)} /> : null}

      <aside className={`sidebar ${open ? "open" : ""}`}>
        <div className="brand-card">
          <div className="brand-mark">
            <Bot size={22} />
          </div>
          <div>
            <p className="eyebrow">Support Ops</p>
            <h1>Donde AI Ops</h1>
          </div>
          <button type="button" className="mobile-close-button" onClick={() => setOpen(false)}>
            <X size={18} />
          </button>
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
                onClick={() => setOpen(false)}
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
              <strong>Secure admin zone</strong>
              <p>Live review, fast actions, clean oversight.</p>
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
          <div className="topbar-copy">
            <p className="eyebrow">Admin Dashboard</p>
            <h2>Same live ops view across desktop and mobile</h2>
          </div>
          <ThemeToggle />
        </header>
        <div className="page-container">{children}</div>
      </main>
    </div>
  );
}
