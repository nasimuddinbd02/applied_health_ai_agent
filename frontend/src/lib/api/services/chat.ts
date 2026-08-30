// Realtime chat service — the WebSocket half of the API tier.
//
// Sits where the other `*Service` classes sit, but over `RealtimeChatClient`
// instead of `HttpClient`: it turns the wire protocol into the handful of
// callbacks a chat UI actually wants, and falls back to the REST endpoint when
// a WebSocket cannot be established (a corporate proxy that strips upgrades,
// say) so the assistant still works.
import { RealtimeChatClient, type ConnectionState, type ServerEvent } from "@/lib/api/realtimeClient";
import type { AgentResponse, AppointmentOption, ChatIdentity, ToolCall } from "@/types";
import { AgentService } from "./agent";

export interface ChatTurn {
  role: "patient" | "agent";
  text: string;
  tools?: ToolCall[];
}

export interface ChatHandlers {
  onTurn: (turn: ChatTurn) => void;
  onHistory: (turns: ChatTurn[]) => void;
  onStatus: (status: string | null) => void;
  onOptions: (options: AppointmentOption[]) => void;
  onIdentity: (identity: ChatIdentity) => void;
  onError: (message: string, retryable: boolean) => void;
  onState: (state: ConnectionState) => void;
}

/** Statuses the server streams while the agent works, in customer language. */
const STATUS_TEXT: Record<string, string> = {
  thinking: "Thinking…",
  working: "Working on it…",
  finding_doctors: "Looking up doctors…",
  checking_availability: "Checking availability…",
  booking_appointment: "Booking your appointment…",
  looking_up_your_record: "Looking up your record…",
  creating_your_record: "Setting up your record…",
  submitting_refill_request: "Submitting your refill request…",
};

let counter = 0;
function newMessageId(): string {
  counter += 1;
  return `msg-${Date.now().toString(36)}-${counter}`;
}

export class ChatService {
  private client: RealtimeChatClient | null = null;
  private useRest = false;
  private restThreadId: string | undefined;
  private restSessionToken: string | undefined;

  constructor(
    private readonly handlers: ChatHandlers,
    private readonly rest: AgentService,
    private readonly getAuthToken: () => string | null,
  ) {}

  // ----------------------------------------------------------------- //
  // Lifecycle
  // ----------------------------------------------------------------- //
  start() {
    if (this.client) return;
    this.client = new RealtimeChatClient({
      getAuthToken: this.getAuthToken,
      onEvent: (event) => this.onEvent(event),
      onState: (state) => {
        this.handlers.onState(state);
        if (state !== "open") this.handlers.onStatus(null);
      },
    });
    this.client.connect();
  }

  stop() {
    this.client?.close();
    this.client = null;
  }

  /** Drop the session and start a fresh conversation (used by "switch user"). */
  reset() {
    this.client?.reset();
    this.restThreadId = undefined;
    this.restSessionToken = undefined;
  }

  // ----------------------------------------------------------------- //
  // Sending
  // ----------------------------------------------------------------- //
  send(text: string) {
    this.handlers.onTurn({ role: "patient", text });
    this.dispatch({ type: "user_message", message_id: newMessageId(), message: text });
  }

  /** The customer tapped an offered slot. Still just a turn — the agent books it. */
  selectOption(option: AppointmentOption) {
    this.handlers.onOptions([]);
    this.dispatch({ type: "select_option", message_id: newMessageId(), option_id: option.id });
  }

  private dispatch(frame: { type: string; message_id: string; message?: string; option_id?: string }) {
    if (this.useRest || !this.client) {
      void this.sendOverRest(frame);
      return;
    }
    this.handlers.onStatus(STATUS_TEXT.thinking);
    this.client.send(frame);
  }

  // ----------------------------------------------------------------- //
  // Receiving
  // ----------------------------------------------------------------- //
  private onEvent(event: ServerEvent) {
    switch (event.type) {
      case "ready":
        if (event.identity?.patient_id) this.handlers.onIdentity(event.identity);
        break;
      case "history":
        this.handlers.onHistory(
          (event.turns ?? []).map((t: any) => ({ role: t.role, text: t.content })),
        );
        break;
      case "ack":
        // A duplicate means the server already ran this turn — stop the spinner
        // rather than waiting for a reply that will never come again.
        if (event.duplicate) this.handlers.onStatus(null);
        break;
      case "agent_status":
        this.handlers.onStatus(STATUS_TEXT[event.status] ?? STATUS_TEXT.working);
        break;
      case "agent_message":
        this.handlers.onStatus(null);
        this.handlers.onTurn({ role: "agent", text: event.message, tools: event.tool_calls });
        break;
      case "appointment_options":
        this.handlers.onOptions(event.options ?? []);
        break;
      case "identity":
        this.handlers.onIdentity({ patient_id: event.patient_id, name: event.name });
        break;
      case "error":
        this.handlers.onStatus(null);
        this.handlers.onError(event.message, Boolean(event.retryable));
        break;
      default:
        break;
    }
  }

  // ----------------------------------------------------------------- //
  // REST fallback
  // ----------------------------------------------------------------- //
  /** Give up on WebSockets for this session and use the request/response API. */
  fallbackToRest() {
    if (this.useRest) return;
    this.useRest = true;
    this.client?.close();
  }

  private async sendOverRest(frame: { message?: string; option_id?: string; message_id: string }) {
    const message = frame.message ?? `Please book slot ${(frame.option_id ?? "").replace("slot-", "")}.`;
    this.handlers.onStatus(STATUS_TEXT.thinking);
    try {
      const res: AgentResponse = await this.rest.chat({
        message,
        message_id: frame.message_id,
        thread_id: this.restThreadId,
        session_token: this.restSessionToken,
      });
      this.restThreadId = res.conversation_id || res.thread_id;
      if (res.session_token) this.restSessionToken = res.session_token;
      if (res.identity?.patient_id) this.handlers.onIdentity(res.identity);
      if (res.options?.length) this.handlers.onOptions(res.options);
      this.handlers.onTurn({ role: "agent", text: res.final_text, tools: res.tool_calls });
    } catch (err: any) {
      this.handlers.onError(err?.message ?? "Something went wrong.", true);
    } finally {
      this.handlers.onStatus(null);
    }
  }
}
