"use client";

import { useId } from "react";

import { usePalette, type Token } from "@/lib/tokens";

interface SparklineProps {
  data: number[];
  width?: number;
  height?: number;
  /** A palette token, or "trend" to colour by direction. Never a literal. */
  tone?: Token | "trend";
  className?: string;
}

export default function Sparkline({
  data,
  width = 68,
  height = 22,
  tone = "trend",
  className = "",
}: SparklineProps) {
  const palette = usePalette();
  // A gradient id has to be unique per instance: two sparklines sharing one id
  // means the second silently paints with the first one's stops.
  const gradientId = useId();

  if (data.length < 2) return null;

  const min = Math.min(...data);
  const max = Math.max(...data);
  const range = max - min || 1;

  const points = data
    .map((val, i) => {
      const x = (i / (data.length - 1)) * width;
      const y = height - ((val - min) / range) * (height - 4) - 2;
      return `${x},${y}`;
    })
    .join(" ");

  const rising = data[data.length - 1] >= data[0];
  const color = palette[tone === "trend" ? (rising ? "positive" : "critical") : tone];
  const lastY = Number(points.split(" ").pop()!.split(",")[1]);

  return (
    <svg
      width={width}
      height={height}
      className={className}
      viewBox={`0 0 ${width} ${height}`}
      aria-hidden="true"
    >
      <defs>
        <linearGradient id={gradientId} x1="0" y1="0" x2="0" y2="1">
          <stop offset="0%" stopColor={color} stopOpacity="0.22" />
          <stop offset="100%" stopColor={color} stopOpacity="0" />
        </linearGradient>
      </defs>
      <polygon points={`0,${height} ${points} ${width},${height}`} fill={`url(#${gradientId})`} />
      <polyline
        points={points}
        fill="none"
        stroke={color}
        strokeWidth="1.25"
        strokeLinecap="round"
        strokeLinejoin="round"
      />
      <circle cx={width} cy={lastY} r="1.75" fill={color} />
    </svg>
  );
}
