"use client";

import { MoonStar, SunMedium } from "lucide-react";
import { useEffect, useState } from "react";

export default function ThemeToggle() {
  const [theme, setTheme] = useState("dark");

  useEffect(() => {
    const saved = localStorage.getItem("dashboard-theme") || "dark";
    document.documentElement.dataset.theme = saved;
    setTheme(saved);
  }, []);

  function toggleTheme() {
    const next = theme === "dark" ? "light" : "dark";
    document.documentElement.dataset.theme = next;
    localStorage.setItem("dashboard-theme", next);
    setTheme(next);
  }

  return (
    <button type="button" className="theme-toggle" onClick={toggleTheme}>
      {theme === "dark" ? <SunMedium size={16} /> : <MoonStar size={16} />}
      <span>{theme === "dark" ? "Light mode" : "Dark mode"}</span>
    </button>
  );
}
