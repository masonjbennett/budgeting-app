"use client";

/**
 * A measured figure with the verdict the API returned beside it.
 *
 * `tone` names a MEANING, not a colour. Claret and bronze are spent only here
 * and on the badges — the moment something decorative uses them the alarm
 * states stop reading as alarms.
 */
type Tone = "positive" | "caution" | "critical" | "info";

interface StatusCardProps {
  label: string;
  value: string;
  status: string;
  tone: Tone;
  description?: string;
}

const TONE: Record<Tone, { text: string; badge: string }> = {
  positive: { text: "text-positive", badge: "badge-positive" },
  caution: { text: "text-caution", badge: "badge-caution" },
  critical: { text: "text-critical", badge: "badge-critical" },
  info: { text: "text-info", badge: "badge-info" },
};

export default function StatusCard({ label, value, status, tone, description }: StatusCardProps) {
  const c = TONE[tone];
  return (
    <div className="card flex flex-col">
      <p className="label">{label}</p>
      <p className={`font-num t-h3 mt-1.5 leading-none font-medium ${c.text}`}>{value}</p>
      <p className="mt-2.5">
        <span className={`badge ${c.badge}`}>{status}</span>
      </p>
      {description && (
        <p className="t-micro mt-2.5 text-muted">{description}</p>
      )}
    </div>
  );
}
