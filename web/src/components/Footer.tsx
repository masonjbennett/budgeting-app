"use client";

export default function Footer() {
  return (
    <footer className="mt-16 pt-6 border-t border-border text-center">
      <p className="text-[0.78rem] text-muted">
        <a href="https://masonjbennett.com" target="_blank" rel="noopener noreferrer" className="text-accent font-medium hover:underline">
          Mason Bennett
        </a>
        {" · "}Next.js + FastAPI{" · "}
        <a href="https://github.com/masonjbennett/budgeting-app" target="_blank" rel="noopener noreferrer" className="text-muted hover:text-accent transition-colors">
          GitHub
        </a>
      </p>
    </footer>
  );
}
