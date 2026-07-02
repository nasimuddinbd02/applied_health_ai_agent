// Appointment-agent chat.
import type { AgentResponse, ChatMessage } from "@/models/types";
import { BaseService } from "./baseService";

export interface AgentRequest {
  patient_id?: number | null;
  message: string;
  thread_id?: string;
}

export class AgentService extends BaseService {
  chat(body: AgentRequest) {
    return this.http.post<AgentResponse>("/api/agent/appointment", body);
  }
  history(threadId: string) {
    return this.http.get<ChatMessage[]>(`/api/agent/appointment/${threadId}/history`);
  }
}
