// Reconnect pacing for the realtime chat client.
//
// Full jitter (a uniform draw from [0, ceiling]) rather than a fixed delay:
// when a chat pod dies it drops every socket it held at the same instant, and
// an unjittered backoff would send all of those clients back through the load
// balancer together, repeatedly.
export const BASE_BACKOFF_MS = 500;
export const MAX_BACKOFF_MS = 30_000;

export function backoffCeiling(attempt: number): number {
  const safe = Math.max(0, Math.floor(attempt));
  // 2 ** big is Infinity; Math.min keeps it at the cap either way.
  return Math.min(MAX_BACKOFF_MS, BASE_BACKOFF_MS * 2 ** safe);
}

export function reconnectDelay(attempt: number, random: () => number = Math.random): number {
  return random() * backoffCeiling(attempt);
}
