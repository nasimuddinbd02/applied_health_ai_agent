// Front-desk (receptionist) read views: today's queue + counters.
import type { QueueEntry, ReceptionOverview } from "@/types";
import { BaseService } from "./base";

export class ReceptionService extends BaseService {
  queue() {
    return this.http.get<QueueEntry[]>("/api/reception/queue");
  }
  overview() {
    return this.http.get<ReceptionOverview>("/api/reception/overview");
  }
}
