"use client";

import { createContext, useContext, useState, useCallback, useRef, ReactNode } from "react";

interface ToastItem {
  id: number;
  message: string;
  type: "success" | "error" | "info";
  exiting?: boolean;
}

interface ToastContextType {
  toast: (message: string, type?: "success" | "error" | "info") => void;
}

const ToastContext = createContext<ToastContextType>({ toast: () => {} });

export function useToast() {
  return useContext(ToastContext);
}

export function ToastProvider({ children }: { children: ReactNode }) {
  const [toasts, setToasts] = useState<ToastItem[]>([]);
  // A ref, not a local: a plain `let` is re-initialised every render, so the
  // counter was permanently 0 and the id was just Date.now(). Two toasts in
  // one millisecond then shared an id, and a React key.
  const nextId = useRef(0);

  const toast = useCallback((message: string, type: "success" | "error" | "info" = "success") => {
    const id = Date.now() + nextId.current++;
    setToasts(prev => [...prev, { id, message, type }]);
    // Start exit animation after 2.5s
    setTimeout(() => {
      setToasts(prev => prev.map(t => t.id === id ? { ...t, exiting: true } : t));
    }, 2500);
    // Remove after exit animation
    setTimeout(() => {
      setToasts(prev => prev.filter(t => t.id !== id));
    }, 2800);
  }, []);

  const iconMap = {
    success: (
      <svg className="w-4 h-4 text-green shrink-0" fill="none" viewBox="0 0 24 24" stroke="currentColor" strokeWidth={2}>
        <path d="M5 13l4 4L19 7" />
      </svg>
    ),
    error: (
      <svg className="w-4 h-4 text-red shrink-0" fill="none" viewBox="0 0 24 24" stroke="currentColor" strokeWidth={2}>
        <path d="M6 18L18 6M6 6l12 12" />
      </svg>
    ),
    info: (
      <svg className="w-4 h-4 text-accent shrink-0" fill="none" viewBox="0 0 24 24" stroke="currentColor" strokeWidth={2}>
        <path d="M13 16h-1v-4h-1m1-4h.01M21 12a9 9 0 11-18 0 9 9 0 0118 0z" />
      </svg>
    ),
  };

  return (
    <ToastContext.Provider value={{ toast }}>
      {children}
      {/* Toast container */}
      <div className="fixed bottom-6 right-6 z-[100] flex flex-col gap-2">
        {toasts.map(t => (
          <div
            key={t.id}
            className={`flex items-center gap-2.5 px-4 py-3 rounded-lg bg-[#171717] border border-[rgba(255,255,255,0.06)] shadow-xl shadow-black/30 ${t.exiting ? "toast-exit" : "toast-enter"}`}
          >
            {iconMap[t.type]}
            <span className="text-[0.82rem] text-slate-200">{t.message}</span>
          </div>
        ))}
      </div>
    </ToastContext.Provider>
  );
}
