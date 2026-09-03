"use client";

interface PageHeaderProps {
  title: string;
  description: string;
  source?: { label: string; href: string };
}

export default function PageHeader({ title, description, source }: PageHeaderProps) {
  return (
    <header className="animate-fade-in mb-8 border-b border-hair pb-5">
      <h1>{title}</h1>
      <p className="t-small mt-1.5 max-w-[62ch] text-muted">{description}</p>
      {source && (
        <p className="t-micro mt-2.5 text-muted">
          <span className="label mr-1.5">Source</span>
          <a href={source.href} target="_blank" rel="noopener noreferrer" className="text-accent hover:underline">
            {source.label}
          </a>
        </p>
      )}
    </header>
  );
}
