import type { Metadata } from "next";
import "./globals.css";

export const metadata: Metadata = {
  title: "Employee Monitor — Workforce monitoring made simple",
  description:
    "Automatic screenshots, multi-monitor support, and an employee review window. Deploy in under 10 minutes.",
  openGraph: {
    title: "Employee Monitor",
    description: "Workforce monitoring made simple.",
    type: "website",
  },
};

export default function RootLayout({
  children,
}: {
  children: React.ReactNode;
}) {
  return (
    <html lang="en">
      <body>{children}</body>
    </html>
  );
}
