// Ops: health + audit/cost.
import type { AuditResponse } from "@/models/types";
import { BaseService } from "./baseService";

export class OpsService extends BaseService {
  health() {
    return this.http.get<{
      status: string;
      provider: string;
      model: string;
      has_provider_key: boolean;
    }>("/health");
  }
  audit() {
    return this.http.get<AuditResponse>("/api/audit");
  }
}
