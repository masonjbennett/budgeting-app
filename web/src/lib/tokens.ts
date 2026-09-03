"use client";

/**
 * Reading the palette back out of CSS, for the things that cannot use a class.
 *
 * Almost everything is styled with a Tailwind utility (`text-critical`,
 * `bg-raise`), which emits `var(--critical)` and therefore follows the theme on
 * its own. Charts are the exception: Recharts takes its colours as JS strings
 * and writes them onto SVG PRESENTATION ATTRIBUTES, and its own class name goes
 * on a wrapping <g> rather than the painted path, so there is no class to hang a
 * rule on.
 *
 * Handing Recharts the literal string "var(--s1)" does work — verified in this
 * engine, a presentation attribute is parsed as CSS and resolves the variable.
 * It is not relied on, because whether it works in Safari and Firefox cannot be
 * checked from here, and the failure mode is a chart drawn in black on a
 * recruiting link opened on a phone. So the values are read back out of the
 * computed style instead, which every engine supports, and the var() string is
 * kept only as the answer for a render where there is no DOM to read.
 *
 * THE POINT IS STILL THAT THERE IS ONE DEFINITION. These names resolve to
 * whatever globals.css currently says; nothing here holds a colour.
 */

import { useSyncExternalStore } from "react";

export type Token =
  | "paper" | "raise" | "card" | "hair" | "hairSoft"
  | "ink" | "body" | "muted" | "faint"
  | "accent" | "positive" | "critical" | "caution" | "info"
  | "s1" | "s2" | "s3" | "s4" | "s5" | "s6" | "s7" | "s8";

/** Token name → the custom property it lives in. The only mapping there is. */
const VAR: Record<Token, string> = {
  paper: "--paper",
  raise: "--raise",
  card: "--card",
  hair: "--hair",
  hairSoft: "--hair-soft",
  ink: "--ink",
  body: "--body-c",
  muted: "--muted",
  faint: "--faint",
  accent: "--accent",
  positive: "--positive",
  critical: "--critical",
  caution: "--caution",
  info: "--info",
  s1: "--s1",
  s2: "--s2",
  s3: "--s3",
  s4: "--s4",
  s5: "--s5",
  s6: "--s6",
  s7: "--s7",
  s8: "--s8",
};

const NAMES = Object.keys(VAR) as Token[];

/**
 * `var(--x)` for a token, for the `style` prop.
 *
 * A custom-property reference in a CSS PROPERTY is universally supported, so
 * this needs no hook and follows the theme on its own. It is only unsafe in an
 * SVG presentation attribute, which is why the charts read resolved values
 * instead. Prefer a Tailwind utility over either where one exists.
 */
export function cssVar(token: Token): string {
  return `var(${VAR[token]})`;
}

/** The categorical series, in the order a chart should spend it. */
export const SERIES: Token[] = ["s1", "s2", "s3", "s4", "s5", "s6", "s7", "s8"];

export type Palette = Record<Token, string>;

/**
 * The answer where there is no DOM to read — server render, and the hydration
 * render that has to match it. A variable reference cannot be a WRONG colour,
 * only an unresolved one; and no chart is server-rendered anyway, because every
 * page returns a skeleton until its data has loaded on the client.
 */
const SSR_PALETTE: Palette = Object.freeze(
  NAMES.reduce((acc, n) => {
    acc[n] = `var(${VAR[n]})`;
    return acc;
  }, {} as Palette),
);

function readFromDom(): Palette {
  const cs = getComputedStyle(document.documentElement);
  return NAMES.reduce((acc, n) => {
    acc[n] = cs.getPropertyValue(VAR[n]).trim() || `var(${VAR[n]})`;
    return acc;
  }, {} as Palette);
}

/* ── The store ──────────────────────────────────────────────────────────
   `useSyncExternalStore` rather than useState + useEffect, for two reasons
   beyond the lint rule. The snapshot must be referentially STABLE or React
   re-renders forever, so the palette is cached and invalidated only when
   something actually changes; and reading it during render rather than after
   one means a chart is never painted once in the wrong theme and then
   corrected.

   Two triggers, because there are three theme states: an explicit choice
   stamps `data-theme` on <html>, and the default "system" setting stamps
   nothing at all, so an OS switch has to be heard separately.              */

let cache: Palette | null = null;
const listeners = new Set<() => void>();
let observer: MutationObserver | null = null;
let mq: MediaQueryList | null = null;

function invalidate() {
  cache = null;
  for (const l of listeners) l();
}

function subscribe(onChange: () => void): () => void {
  listeners.add(onChange);
  if (listeners.size === 1) {
    observer = new MutationObserver(invalidate);
    observer.observe(document.documentElement, {
      attributes: true,
      attributeFilter: ["data-theme"],
    });
    mq = window.matchMedia("(prefers-color-scheme: dark)");
    mq.addEventListener("change", invalidate);
  }
  return () => {
    listeners.delete(onChange);
    if (listeners.size === 0) {
      observer?.disconnect();
      observer = null;
      mq?.removeEventListener("change", invalidate);
      mq = null;
    }
  };
}

function getSnapshot(): Palette {
  if (cache === null) cache = readFromDom();
  return cache;
}

function getServerSnapshot(): Palette {
  return SSR_PALETTE;
}

/** The current palette, re-read whenever the theme changes. */
export function usePalette(): Palette {
  return useSyncExternalStore(subscribe, getSnapshot, getServerSnapshot);
}
