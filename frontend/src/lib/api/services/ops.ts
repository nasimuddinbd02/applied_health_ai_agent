// Ops: health + audit/cost.
import type { AuditResponse } from "@/types";
import { BaseService } from "./base";

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
