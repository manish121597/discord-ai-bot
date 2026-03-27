import "./globals.css";
import AppShell from "../components/AppShell";

export const metadata = {
  title: "Donde AI Ops",
  description: "Premium AI support operations dashboard",
};

export default function RootLayout({ children }) {
  return (
    <html lang="en" data-theme="dark">
      <body>
        <AppShell>{children}</AppShell>
      </body>
    </html>
  );
}
