"use client";

import { useEffect, useState } from "react";

import { usePalette, type Token } from "@/lib/tokens";

interface RingChartProps {
  /** 0-100. */
  value: number;
  size?: number;
  strokeWidth?: number;
  tone?: Token;
  label?: string;
  /** Two or three words. Anything longer belongs in `caption` — the centre of
   *  a 102px dial is not a paragraph, and a sentence put here wraps over the
   *  arc it is describing. */
  sublabel?: string;
  /** The long form, below the dial rather than inside it. */
  caption?: string;
  className?: string;
}

export default function RingChart({
  value,
  size = 108,
  strokeWidth = 6,
  tone = "accent",
  label,
  sublabel,
  caption,
  className = "",
}: RingChartProps) {
  const palette = usePalette();
  const [animated, setAnimated] = useState(0);
  const radius = (size - strokeWidth) / 2;
  const circumference = 2 * Math.PI * radius;
  const offset = circumference - (animated / 100) * circumference;

  useEffect(() => {
    const timer = setTimeout(() => setAnimated(Math.min(value, 100)), 80);
    return () => clearTimeout(timer);
  }, [value]);

  return (
    <div className={`ring-container ${className}`}>
      <div className="ring-dial">
      <svg width={size} height={size}>
        <circle
          cx={size / 2}
          cy={size / 2}
          r={radius}
          fill="none"
          stroke={palette.hairSoft}
          strokeWidth={strokeWidth}
        />
        <circle
          cx={size / 2}
          cy={size / 2}
          r={radius}
          fill="none"
          stroke={palette[tone]}
          strokeWidth={strokeWidth}
          strokeDasharray={circumference}
          strokeDashoffset={offset}
          strokeLinecap="butt"
          style={{ transition: "stroke-dashoffset 0.9s cubic-bezier(0.22, 1, 0.36, 1)" }}
        />
      </svg>
      <div className="absolute inset-0 flex flex-col items-center justify-center">
        {label && <span className="font-num t-h3 leading-none font-medium text-ink">{label}</span>}
        {sublabel && <span className="t-micro mt-1 text-muted">{sublabel}</span>}
      </div>
      </div>
      {/* Outside the dial, so it can be a sentence. Width-capped so a long one
          makes the card taller rather than wider — a chart card in a four-up
          grid that grows sideways drags the other three out of alignment. */}
      {caption && (
        <p className="t-micro mt-2.5 max-w-[13.5rem] text-center leading-snug text-muted">
          {caption}
        </p>
      )}
    </div>
  );
}
