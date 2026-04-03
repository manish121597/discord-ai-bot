"use client";

import { MoonStar } from "lucide-react";

export default function ThemeToggle() {
  return (
    <div className="theme-toggle theme-fixed">
      <MoonStar size={16} />
      <span>Unified dark theme</span>
    </div>
  );
}
