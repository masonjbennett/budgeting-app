"use client";

interface StatusCardProps {
  label: string;
  value: string;
  status: string;
  color: "green" | "yellow" | "red" | "blue";
  description?: string;
}

const colorMap = {
  green: { text: "text-green", bg: "bg-green/10", dot: "bg-green" },
  yellow: { text: "text-yellow", bg: "bg-yellow/10", dot: "bg-yellow" },
  red: { text: "text-red", bg: "bg-red/10", dot: "bg-red" },
  blue: { text: "text-accent", bg: "bg-accent/10", dot: "bg-accent" },
};

export default function StatusCard({ label, value, status, color, description }: StatusCardProps) {
  const c = colorMap[color];
  return (
    <div className="card animate-fade-in">
      <p className="text-[0.6875rem] uppercase tracking-[0.06em] text-muted font-medium">{label}</p>
      <p className={`text-[1.75rem] font-bold mt-1 leading-tight font-num tracking-tight ${c.text}`}>
        {value}
      </p>
      <div className={`inline-flex items-center gap-1.5 mt-2 px-2 py-0.5 rounded-full ${c.bg}`}>
        <span className={`w-1.5 h-1.5 rounded-full ${c.dot}`} />
        <span className={`text-[0.6875rem] font-medium ${c.text}`}>{status}</span>
      </div>
      {description && (
        <p className="text-[0.6875rem] text-muted mt-2 leading-relaxed">{description}</p>
      )}
    </div>
  );
}
