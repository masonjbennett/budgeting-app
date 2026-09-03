"use client";

/**
 * `prefers-reduced-motion`, read during render rather than after one.
 *
 * The obvious version — `useState(false)` plus an effect that measures and
 * calls setState — is what the lint rule objects to, and it is also wrong on
 * its own terms: the component renders once WITH motion and then corrects
 * itself, so someone who asked for less motion gets a frame of it anyway.
 * A `useSyncExternalStore` snapshot is read before the first paint.
 *
 * `getServerSnapshot` is false because a server has no viewer to ask. That is
 * the safe direction: the CSS `@media (prefers-reduced-motion: reduce)` block
 * in globals.css already neutralises every transition and animation, so this
 * hook only governs the JS count-up, whose fallback is the finished number.
 */

import { useSyncExternalStore } from "react";

const QUERY = "(prefers-reduced-motion: reduce)";

function subscribe(onChange: () => void): () => void {
  const mq = window.matchMedia(QUERY);
  mq.addEventListener("change", onChange);
  return () => mq.removeEventListener("change", onChange);
}

function getSnapshot(): boolean {
  return window.matchMedia(QUERY).matches;
}

function getServerSnapshot(): boolean {
  return false;
}

export function useReducedMotion(): boolean {
  return useSyncExternalStore(subscribe, getSnapshot, getServerSnapshot);
}
