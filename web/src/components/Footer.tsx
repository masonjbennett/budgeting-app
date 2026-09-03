"use client";

export default function Footer() {
  return (
    <footer className="mt-14 border-t border-hair pt-5">
      <p className="t-micro text-muted">
        <a
          href="https://masonjbennett.com"
          target="_blank"
          rel="noopener noreferrer"
          className="font-medium text-accent hover:underline"
        >
          Mason Bennett
        </a>
        {" · "}Next.js + FastAPI{" · "}
        <a
          href="https://github.com/masonjbennett/budgeting-app"
          target="_blank"
          rel="noopener noreferrer"
          className="transition-colors hover:text-accent"
        >
          GitHub
        </a>
      </p>
    </footer>
  );
}
