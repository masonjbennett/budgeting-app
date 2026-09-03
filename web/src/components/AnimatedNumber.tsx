"use client";

import { useEffect, useRef, useState } from "react";

import { useReducedMotion } from "@/lib/media";

/**
 * A figure that counts up to its value.
 *
 * This is React state and a requestAnimationFrame loop, which is why it is
 * allowed where chart-library entry animation is not: if the loop never runs,
 * the number is simply there. It cannot leave a blank, which is exactly the
 * failure Recharts' pie animation produces.
 *
 * Reduced motion is handled by RENDERING the real value rather than by setting
 * state to it — the effect returns before it starts a loop, so `display` is
 * left stale on purpose and never read. Correcting it with a setState would
 * mean rendering the old number once and then the right one, which is a frame
 * of the very motion that was asked not to happen.
 *
 * It formats but does not decide anything — same standing as `fmt` and `pct`.
 */
interface AnimatedNumberProps {
  value: number;
  prefix?: string;
  decimals?: number;
  duration?: number;
  className?: string;
  /** Usually the exact figure, where the displayed one is abbreviated. */
  title?: string;
}

export default function AnimatedNumber({
  value,
  prefix = "$",
  decimals = 0,
  duration = 700,
  className = "",
  title,
}: AnimatedNumberProps) {
  const reduced = useReducedMotion();
  const [display, setDisplay] = useState(value);
  const prevValue = useRef(value);
  const frameRef = useRef<number>(0);

  useEffect(() => {
    const from = prevValue.current;
    const to = value;
    prevValue.current = value;

    if (from === to || reduced) return;

    const start = performance.now();
    const animate = (now: number) => {
      const progress = Math.min((now - start) / duration, 1);
      const eased = 1 - Math.pow(1 - progress, 3);
      setDisplay(from + (to - from) * eased);
      if (progress < 1) frameRef.current = requestAnimationFrame(animate);
      else setDisplay(to);
    };
    frameRef.current = requestAnimationFrame(animate);
    return () => cancelAnimationFrame(frameRef.current);
  }, [value, duration, reduced]);

  const shown = reduced ? value : display;
  const formatted = `${prefix}${shown.toLocaleString("en-US", {
    minimumFractionDigits: decimals,
    maximumFractionDigits: decimals,
  })}`;

  return (
    <span className={`font-num ${className}`} title={title}>
      {formatted}
    </span>
  );
}
