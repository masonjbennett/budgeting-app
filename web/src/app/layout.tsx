import type { Metadata } from "next";
import { Inter } from "next/font/google";

import "./globals.css";
import CommandPalette from "@/components/CommandPalette";
import Sidebar from "@/components/Sidebar";
import { ToastProvider } from "@/components/Toast";
import { FinanceProvider } from "@/context/FinanceContext";

const inter = Inter({ subsets: ["latin"], variable: "--font-inter" });

export const metadata: Metadata = {
  title: "Budget Tracker — Mason Bennett",
  description:
    "Personal finance planning: 2026 federal and state tax estimation, budgeting, "
    + "debt payoff, investment projections and a Monte Carlo FIRE model.",
};

export default function RootLayout({ children }: { children: React.ReactNode }) {
  return (
    <html lang="en" className={`${inter.variable} h-full`}>
      <body className="flex min-h-full bg-bg antialiased">
        <ToastProvider>
          <FinanceProvider>
            <Sidebar />
            <main className="flex-1 p-6 lg:ml-60 lg:p-8">
              <div className="mx-auto max-w-6xl">{children}</div>
            </main>
            <CommandPalette />
          </FinanceProvider>
        </ToastProvider>
      </body>
    </html>
  );
}
