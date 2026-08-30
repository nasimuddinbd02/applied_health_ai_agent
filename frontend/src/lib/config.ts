// Frontend configuration read from NEXT_PUBLIC_* environment variables.
//
// There are two different "where is the API" answers, and getting them
// confused is the classic Next.js deployment bug:
//
//   * The **browser** needs a URL it can reach from outside the cluster.
//     NEXT_PUBLIC_* values are inlined at *build* time, so a hard-coded one
//     would bake an environment into the image.
//   * **Server Components** run inside the cluster and must use an absolute
//     URL — a relative path has no origin to resolve against on the server.
//     INTERNAL_API_BASE is a plain (non-public) variable, so it is read at
//     *run* time and can differ per environment without a rebuild.
//
// Setting NEXT_PUBLIC_API_BASE to the empty string means "same origin": the
// browser calls the page's own host and the ingress routes /api and /ws to the
// backend. That is what lets one image ship to every environment.

const PUBLIC_API_BASE = process.env.NEXT_PUBLIC_API_BASE;
const PUBLIC_WS_BASE = process.env.NEXT_PUBLIC_WS_BASE;
const DEV_FALLBACK = "http://localhost:8000";

function onServer(): boolean {
  return typeof window === "undefined";
}

export class AppConfig {
  /** Base URL for REST calls, correct for whichever side is asking. */
  static get apiBase(): string {
    if (onServer()) {
      return process.env.INTERNAL_API_BASE || PUBLIC_API_BASE || DEV_FALLBACK;
    }
    // Explicitly empty is a deliberate "use my own origin", not a missing value.
    if (PUBLIC_API_BASE === "") return window.location.origin;
    return PUBLIC_API_BASE || DEV_FALLBACK;
  }

  /** WebSocket origin for the chat gateway (`wss://` behind TLS). */
  static get wsBase(): string {
    if (PUBLIC_WS_BASE) return PUBLIC_WS_BASE;
    if (onServer()) {
      // Only ever used to build a URL handed to the browser; the socket itself
      // is opened client-side.
      return (PUBLIC_API_BASE || DEV_FALLBACK).replace(/^http/, "ws");
    }
    if (PUBLIC_API_BASE === "") return window.location.origin.replace(/^http/, "ws");
    return (PUBLIC_API_BASE || DEV_FALLBACK).replace(/^http/, "ws");
  }
}
