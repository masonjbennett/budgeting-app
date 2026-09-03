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
      <svg className="h-4 w-4 shrink-0 text-positive" fill="none" viewBox="0 0 24 24" stroke="currentColor" strokeWidth={2}>
        <path d="M5 13l4 4L19 7" />
      </svg>
    ),
    error: (
      <svg className="h-4 w-4 shrink-0 text-critical" fill="none" viewBox="0 0 24 24" stroke="currentColor" strokeWidth={2}>
        <path d="M6 18L18 6M6 6l12 12" />
      </svg>
    ),
    info: (
      <svg className="h-4 w-4 shrink-0 text-info" fill="none" viewBox="0 0 24 24" stroke="currentColor" strokeWidth={2}>
        <path d="M13 16h-1v-4h-1m1-4h.01M21 12a9 9 0 11-18 0 9 9 0 0118 0z" />
      </svg>
    ),
  };

  return (
    <ToastContext.Provider value={{ toast }}>
      {children}
      <div className="fixed right-5 bottom-5 z-[100] flex flex-col gap-2">
        {toasts.map(t => (
          <div
            key={t.id}
            className={`t-small flex items-center gap-2.5 rounded-sm border border-hair bg-card px-3.5 py-2.5 text-ink ${
              t.exiting ? "toast-exit" : "toast-enter"
            }`}
          >
            {iconMap[t.type]}
            <span>{t.message}</span>
          </div>
        ))}
      </div>
    </ToastContext.Provider>
  );
}
