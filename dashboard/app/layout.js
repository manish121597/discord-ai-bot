import "./globals.css";

export const metadata = {
  title: "Admin Dashboard",
  description: "Donde Ticket Manager Admin Panel",
};

export default function RootLayout({ children }) {
  return (
    <html lang="en">
      <body>{children}</body>
    </html>
  );
}
