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
      {/* Backdrop */}
      <div className="fixed inset-0 z-[200] bg-black/60 backdrop-blur-sm" onClick={() => setOpen(false)} />

      {/* Dialog */}
      <div className="fixed top-[20%] left-1/2 -translate-x-1/2 z-[201] w-full max-w-lg animate-fade-in">
        <div className="bg-[#09090b] border border-[#171717] rounded-xl shadow-2xl shadow-black/50 overflow-hidden">
          {/* Search */}
          <div className="flex items-center gap-3 px-4 py-3 border-b border-[#171717]">
            <svg className="w-4 h-4 text-slate-500 shrink-0" fill="none" viewBox="0 0 24 24" stroke="currentColor" strokeWidth={2}>
              <path d="M21 21l-6-6m2-5a7 7 0 11-14 0 7 7 0 0114 0z" />
            </svg>
            <input
              ref={inputRef}
              value={query}
              onChange={e => { setQuery(e.target.value); setSelected(0); }}
              onKeyDown={handleKeyDown}
              placeholder="Type a command or search..."
              className="flex-1 bg-transparent text-[0.9rem] text-white placeholder-slate-600 outline-none border-none p-0"
            />
            <kbd className="text-[0.6rem] text-slate-600 bg-[#171717] px-1.5 py-0.5 rounded border border-[rgba(255,255,255,0.08)]">ESC</kbd>
          </div>

          {/* Results */}
          <div className="max-h-[20rem] overflow-y-auto py-2">
            {filtered.length === 0 ? (
              <p className="px-4 py-8 text-center text-[0.82rem] text-slate-600">No results found</p>
            ) : (
              filtered.map((cmd, i) => (
                <button
                  key={cmd.href}
                  onClick={() => handleSelect(cmd.href)}
                  onMouseEnter={() => setSelected(i)}
                  className={`w-full flex items-center gap-3 px-4 py-2.5 text-left transition-colors ${
                    i === selected ? "bg-blue-500/10 text-white" : "text-slate-400 hover:text-slate-300"
                  }`}
                >
                  <svg className={`w-4 h-4 shrink-0 ${i === selected ? "text-blue-400" : "text-slate-600"}`} fill="none" viewBox="0 0 24 24" stroke="currentColor" strokeWidth={1.5}>
                    <path d="M13.5 4.5L21 12m0 0l-7.5 7.5M21 12H3" />
                  </svg>
                  <span className="text-[0.85rem]">{cmd.name}</span>
                  <span className="ml-auto text-[0.68rem] text-slate-600">{cmd.section}</span>
                </button>
              ))
            )}
          </div>

          {/* Footer */}
          <div className="border-t border-[#171717] px-4 py-2 flex items-center gap-4 text-[0.65rem] text-slate-600">
            <span><kbd className="bg-[#171717] px-1 py-0.5 rounded border border-[rgba(255,255,255,0.08)] mr-1">↑↓</kbd> navigate</span>
            <span><kbd className="bg-[#171717] px-1 py-0.5 rounded border border-[rgba(255,255,255,0.08)] mr-1">↵</kbd> select</span>
            <span><kbd className="bg-[#171717] px-1 py-0.5 rounded border border-[rgba(255,255,255,0.08)] mr-1">esc</kbd> close</span>
          </div>
        </div>
      </div>
    </>
  );
}
