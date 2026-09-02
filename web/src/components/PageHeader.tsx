"use client";

interface PageHeaderProps {
  title: string;
  description: string;
  source?: { label: string; href: string };
}

export default function PageHeader({ title, description, source }: PageHeaderProps) {
  return (
    <div className="mb-8 animate-fade-in">
      <h1 className="text-[1.85rem] font-bold text-white leading-tight">{title}</h1>
      <div className="section-divider mt-2" />
      <p className="text-dim text-[0.88rem] leading-relaxed max-w-2xl">{description}</p>
      {source && (
        <div className="mt-3 inline-flex items-center gap-1.5 px-3 py-1.5 bg-accent/5 border border-accent/20 rounded-lg">
          <span className="text-[0.75rem] text-muted">Source:</span>
          <a href={source.href} target="_blank" rel="noopener noreferrer" className="text-[0.75rem] text-accent font-medium hover:underline">
            {source.label}
          </a>
        </div>
      )}
    </div>
  );
}
