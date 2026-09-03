"use client";

import { useState, useEffect, useRef } from "react";
import { useRouter } from "next/navigation";

const COMMANDS = [
  { name: "Dashboard", href: "/", section: "Navigate" },
  { name: "Income Setup", href: "/income", section: "Navigate" },
  { name: "Budget Builder", href: "/budget", section: "Navigate" },
  { name: "Expense Tracker", href: "/expenses", section: "Navigate" },
  { name: "Net Worth", href: "/net-worth", section: "Navigate" },
  { name: "Savings Goals", href: "/goals", section: "Navigate" },
  { name: "Debt Payoff", href: "/debt", section: "Navigate" },
  { name: "Compare Scenarios", href: "/compare", section: "Navigate" },
  { name: "Investments", href: "/investments", section: "Navigate" },
  { name: "FIRE Calculator", href: "/fire", section: "Navigate" },
  { name: "Tax Estimator", href: "/tax", section: "Navigate" },
  { name: "Settings", href: "/data", section: "Navigate" },
];

export default function CommandPalette() {
  const [open, setOpen] = useState(false);
  const [query, setQuery] = useState("");
  const [selected, setSelected] = useState(0);
  const inputRef = useRef<HTMLInputElement>(null);
  const router = useRouter();

  // Cmd+K to open
  useEffect(() => {
    const handler = (e: KeyboardEvent) => {
      if ((e.metaKey || e.ctrlKey) && e.key === "k") {
        e.preventDefault();
        setOpen(prev => !prev);
        setQuery("");
        setSelected(0);
      }
      if (e.key === "Escape") setOpen(false);
    };
    window.addEventListener("keydown", handler);
    return () => window.removeEventListener("keydown", handler);
  }, []);

  // Focus input on open
  useEffect(() => {
    if (open) setTimeout(() => inputRef.current?.focus(), 50);
  }, [open]);

  const filtered = COMMANDS.filter(c =>
    c.name.toLowerCase().includes(query.toLowerCase())
  );

  const handleSelect = (href: string) => {
    router.push(href);
    setOpen(false);
    setQuery("");
  };

  const handleKeyDown = (e: React.KeyboardEvent) => {
    if (e.key === "ArrowDown") {
      e.preventDefault();
      setSelected(prev => Math.min(prev + 1, filtered.length - 1));
    } else if (e.key === "ArrowUp") {
      e.preventDefault();
      setSelected(prev => Math.max(prev - 1, 0));
    } else if (e.key === "Enter" && filtered[selected]) {
      handleSelect(filtered[selected].href);
    }
  };

  if (!open) return null;

  return (
    <>
      <div className="fixed inset-0 z-[200] bg-ink/35" onClick={() => setOpen(false)} />

      <div className="animate-fade-in fixed top-[18%] left-1/2 z-[201] w-full max-w-lg -translate-x-1/2 px-4">
        <div className="overflow-hidden rounded-md border border-hair bg-card">
          <div className="flex items-center gap-2.5 border-b border-hair px-3.5 py-2.5">
            <svg className="h-4 w-4 shrink-0 text-faint" fill="none" viewBox="0 0 24 24" stroke="currentColor" strokeWidth={2}>
              <path d="M21 21l-6-6m2-5a7 7 0 11-14 0 7 7 0 0114 0z" />
            </svg>
            <input
              ref={inputRef}
              value={query}
              onChange={e => { setQuery(e.target.value); setSelected(0); }}
              onKeyDown={handleKeyDown}
              placeholder="Go to…"
              className="t-small flex-1 border-none bg-transparent p-0 text-ink focus:shadow-none"
            />
            <kbd className="label rounded-xs border border-hair px-1.5 py-0.5">esc</kbd>
          </div>

          <div className="max-h-[19rem] overflow-y-auto py-1.5">
            {filtered.length === 0 ? (
              <p className="t-small px-4 py-7 text-center text-muted">Nothing matches that.</p>
            ) : (
              filtered.map((cmd, i) => (
                <button
                  key={cmd.href}
                  onClick={() => handleSelect(cmd.href)}
                  onMouseEnter={() => setSelected(i)}
                  className={`t-small flex w-full items-center gap-2.5 px-3.5 py-2 text-left transition-colors ${
                    i === selected ? "bg-raise text-ink" : "text-body"
                  }`}
                >
                  <span
                    className={`h-3 w-[2px] shrink-0 ${i === selected ? "bg-accent" : "bg-transparent"}`}
                    aria-hidden="true"
                  />
                  <span>{cmd.name}</span>
                  <span className="label ml-auto">{cmd.section}</span>
                </button>
              ))
            )}
          </div>

          <div className="flex items-center gap-4 border-t border-hair px-3.5 py-2">
            {[["↑↓", "navigate"], ["↵", "select"], ["esc", "close"]].map(([k, what]) => (
              <span key={what} className="t-micro text-muted">
                <kbd className="mr-1 rounded-xs border border-hair px-1 py-0.5 font-mono text-[10px]">{k}</kbd>
                {what}
              </span>
            ))}
          </div>
        </div>
      </div>
    </>
  );
}
