import type { Metadata } from "next";
import { Instrument_Serif, JetBrains_Mono, Space_Grotesk } from "next/font/google";

import "./globals.css";
import CommandPalette from "@/components/CommandPalette";
import Nav from "@/components/Nav";
import { ToastProvider } from "@/components/Toast";
import { FinanceProvider } from "@/context/FinanceContext";

/* The site's trio. Instrument Serif has one weight and that is the point —
   it carries titles and the single hero figure per screen, nothing else. */
const display = Instrument_Serif({
  subsets: ["latin"],
  weight: "400",
  variable: "--font-instrument-serif",
  display: "swap",
});
const sans = Space_Grotesk({
  subsets: ["latin"],
  weight: ["400", "500", "600", "700"],
  variable: "--font-space-grotesk",
  display: "swap",
});
const mono = JetBrains_Mono({
  subsets: ["latin"],
  weight: ["400", "500", "700"],
  variable: "--font-jetbrains-mono",
  display: "swap",
});

export const metadata: Metadata = {
  title: "Budget Planner — Mason Bennett",
  description:
    "A planning instrument for personal finance: 2026 federal and state tax "
    + "estimation, budgeting, debt payoff strategy, and a Monte Carlo retirement "
    + "model. Every figure is calculated server-side from published tax law.",
};

/* Applies a stored theme before first paint. Without it the page renders in
   the OS theme and then flips, which is worse than having no toggle. Inline
   and synchronous on purpose — a deferred script is a visible flash. */
const THEME_INIT = `
try {
  var t = localStorage.getItem("mjb_budget_theme");
  if (t === "dark" || t === "light") document.documentElement.dataset.theme = t;
} catch (e) {}
`;

export default function RootLayout({ children }: { children: React.ReactNode }) {
  return (
    <html
      lang="en"
      className={`${display.variable} ${sans.variable} ${mono.variable}`}
      suppressHydrationWarning
    >
      <head>
        <script dangerouslySetInnerHTML={{ __html: THEME_INIT }} />
      </head>
      <body className="min-h-full">
        <ToastProvider>
          <FinanceProvider>
            <Nav />
            {/* pt-14 clears the mobile bar; lg:pl-[13rem] clears the rail. */}
            <main className="pt-14 lg:pt-0 lg:pl-[13rem]">
              <div className="mx-auto max-w-[1120px] px-5 py-7 sm:px-7 lg:px-9 lg:py-9">
                {children}
              </div>
            </main>
            <CommandPalette />
          </FinanceProvider>
        </ToastProvider>
      </body>
    </html>
  );
}
