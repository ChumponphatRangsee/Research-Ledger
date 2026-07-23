import type { Metadata } from "next";
import { Geist, Geist_Mono } from "next/font/google";
import Link from "next/link";

import "./globals.css";

const geistSans = Geist({
  variable: "--font-geist-sans",
  subsets: ["latin"],
});

const geistMono = Geist_Mono({
  variable: "--font-geist-mono",
  subsets: ["latin"],
});

export const metadata: Metadata = {
  title: "InvestFlow-AI",
  description: "Semi-automated financial research with human-in-the-loop decisions",
};

export default function RootLayout({
  children,
}: Readonly<{
  children: React.ReactNode;
}>) {
  return (
    <html lang="en">
      <body className={`${geistSans.variable} ${geistMono.variable} font-sans`}>
        <header className="border-b border-border bg-card">
          <div className="mx-auto flex h-14 max-w-7xl items-center justify-between px-4">
            <Link href="/" className="text-lg font-semibold tracking-tight">
              InvestFlow<span className="text-primary">-AI</span>
            </Link>
            <nav className="flex items-center gap-6 text-sm font-medium text-muted-foreground">
              <Link href="/" className="hover:text-foreground transition-colors">
                Dashboard
              </Link>
              <Link href="/inbox" className="hover:text-foreground transition-colors">
                Inbox
              </Link>
              <Link href="/screener" className="hover:text-foreground transition-colors">
                Screener
              </Link>
              <Link href="/portfolio" className="hover:text-foreground transition-colors">
                Portfolio
              </Link>
            </nav>
          </div>
        </header>
        <main className="mx-auto max-w-7xl px-4 py-8">{children}</main>
      </body>
    </html>
  );
}
