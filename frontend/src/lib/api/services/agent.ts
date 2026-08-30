// Appointment-agent chat over REST.
//
// The primary transport is the WebSocket gateway (`chatService` /
// `realtimeClient`); this is the fallback for clients that cannot hold a
// socket. Same turn, same idempotency, no streaming.
import type { AgentResponse, ChatMessage } from "@/types";
import { BaseService } from "./base";

export interface AgentRequest {
  message: string;
  /** Conversation to continue (the backend still calls it thread_id). */
  thread_id?: string;
  /** Idempotency key for this turn — a resend with the same id is ignored. */
  message_id?: string;
  /** Guest session token from a previous reply, so identity persists. */
  session_token?: string;
}

export class AgentService extends BaseService {
  chat(body: AgentRequest) {
    return this.http.post<AgentResponse>("/api/agent/appointment", body);
  }
  history(threadId: string) {
    return this.http.get<ChatMessage[]>(`/api/agent/appointment/${threadId}/history`);
  }
}
