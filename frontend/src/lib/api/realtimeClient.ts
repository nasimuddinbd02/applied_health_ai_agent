// The WebSocket transport to the chat gateway.
//
// Mirrors `httpClient.ts` — it knows how to talk to the backend and nothing
// about chat. Everything above it (`services/chat.ts`, the React components)
// deals in events, never in sockets.
//
// What it guarantees:
//   * reconnect with exponential backoff + jitter, so a pod restart does not
//     produce a thundering herd of clients hitting the load balancer at once;
//   * resume: the guest session token and conversation id are remembered, so a
//     reconnect (or a page refresh) continues the same conversation;
//   * outbound messages are queued while offline and flushed on reconnect,
//     each keeping its original message_id — the server de-duplicates, so a
//     resend can never book twice.
import { AppConfig } from "@/lib/config";
import { reconnectDelay } from "@/lib/backoff";

export type ServerEvent = { type: string; [key: string]: any };
export type ConnectionState = "connecting" | "open" | "reconnecting" | "closed";

export interface RealtimeClientOptions {
  /** Bearer token for a logged-in user. Read lazily, on every connect. */
  getAuthToken?: () => string | null;
  onEvent: (event: ServerEvent) => void;
  onState?: (state: ConnectionState) => void;
}

const SESSION_KEY = "ch_chat_session";
const CONVERSATION_KEY = "ch_chat_conversation";

export class RealtimeChatClient {
  private socket: WebSocket | null = null;
  private state: ConnectionState = "closed";
  private attempt = 0;
  private reconnectTimer: ReturnType<typeof setTimeout> | null = null;
  private watchdog: ReturnType<typeof setTimeout> | null = null;
  private heartbeatSeconds = 25;
  private pending: object[] = [];
  private closedByUs = false;

  constructor(private readonly options: RealtimeClientOptions) {}

  // ----------------------------------------------------------------- //
  // Session (survives a reconnect and a page refresh)
  // ----------------------------------------------------------------- //
  private read(key: string): string | null {
    try {
      return sessionStorage.getItem(key);
    } catch {
      return null; // private browsing / storage disabled
    }
  }

  private write(key: string, value: string | null) {
    try {
      if (value) sessionStorage.setItem(key, value);
      else sessionStorage.removeItem(key);
    } catch {
      // Nothing to do — we just lose resume across a refresh.
    }
  }

  get conversationId(): string | null {
    return this.read(CONVERSATION_KEY);
  }

  /** Forget the session so the next connect starts a brand-new conversation. */
  reset() {
    this.write(SESSION_KEY, null);
    this.write(CONVERSATION_KEY, null);
  }

  // ----------------------------------------------------------------- //
  // Connection
  // ----------------------------------------------------------------- //
  private url(): string {
    const params = new URLSearchParams();
    // A logged-in user's JWT wins; otherwise replay the guest session token the
    // server minted for us, so we keep the identity it resolved.
    const token = this.options.getAuthToken?.() ?? null;
    const session = token || this.read(SESSION_KEY);
    if (session) params.set("token", session);
    const conversation = this.read(CONVERSATION_KEY);
    if (conversation) params.set("conversation_id", conversation);
    const query = params.toString();
    return `${AppConfig.wsBase}/ws/chat${query ? `?${query}` : ""}`;
  }

  connect() {
    if (typeof window === "undefined") return;
    if (this.socket && (this.state === "open" || this.state === "connecting")) return;
    this.closedByUs = false;
    this.setState(this.attempt === 0 ? "connecting" : "reconnecting");

    const socket = new WebSocket(this.url());
    this.socket = socket;

    socket.onopen = () => {
      this.attempt = 0;
      this.setState("open");
      this.armWatchdog();
      this.flush();
    };
    socket.onmessage = (raw) => this.onMessage(raw);
    socket.onerror = () => socket.close();
    socket.onclose = () => {
      this.socket = null;
      this.clearWatchdog();
      if (this.closedByUs) {
        this.setState("closed");
        return;
      }
      this.setState("reconnecting");
      this.scheduleReconnect();
    };
  }

  close() {
    this.closedByUs = true;
    if (this.reconnectTimer) clearTimeout(this.reconnectTimer);
    this.reconnectTimer = null;
    this.clearWatchdog();
    this.socket?.close(1000, "client closed");
    this.socket = null;
    this.setState("closed");
  }

  private scheduleReconnect() {
    if (this.reconnectTimer) return;
    const delay = reconnectDelay(this.attempt);
    this.attempt += 1;
    this.reconnectTimer = setTimeout(() => {
      this.reconnectTimer = null;
      this.connect();
    }, delay);
  }

  // ----------------------------------------------------------------- //
  // Liveness
  // ----------------------------------------------------------------- //
  private armWatchdog() {
    this.clearWatchdog();
    // The server pings every `heartbeatSeconds`. Silence for well over two
    // intervals means the connection is dead even though the socket looks open
    // (a dropped route, a sleeping laptop) — tear it down and reconnect.
    this.watchdog = setTimeout(() => {
      this.socket?.close(4008, "no heartbeat");
    }, this.heartbeatSeconds * 2500);
  }

  private clearWatchdog() {
    if (this.watchdog) clearTimeout(this.watchdog);
    this.watchdog = null;
  }

  // ----------------------------------------------------------------- //
  // Frames
  // ----------------------------------------------------------------- //
  private onMessage(raw: MessageEvent) {
    this.armWatchdog();
    let event: ServerEvent;
    try {
      event = JSON.parse(raw.data);
    } catch {
      return;
    }

    if (event.type === "ping") {
      this.rawSend({ type: "pong" });
      return;
    }
    if (event.type === "ready") {
      if (event.session_token) this.write(SESSION_KEY, event.session_token);
      if (event.conversation_id) this.write(CONVERSATION_KEY, event.conversation_id);
      if (event.heartbeat_seconds) this.heartbeatSeconds = event.heartbeat_seconds;
    }
    this.options.onEvent(event);
  }

  /** Queue-and-forget: delivered now if connected, on reconnect otherwise. */
  send(frame: object) {
    if (!this.rawSend(frame)) {
      this.pending.push(frame);
      this.connect();
    }
  }

  private rawSend(frame: object): boolean {
    if (this.socket?.readyState !== WebSocket.OPEN) return false;
    this.socket.send(JSON.stringify(frame));
    return true;
  }

  private flush() {
    const queued = this.pending;
    this.pending = [];
    for (const frame of queued) {
      if (!this.rawSend(frame)) this.pending.push(frame);
    }
  }

  private setState(state: ConnectionState) {
    if (this.state === state) return;
    this.state = state;
    this.options.onState?.(state);
  }
}
