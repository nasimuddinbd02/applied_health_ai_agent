// Base class for the REST feature services — holds the injected HTTP client.
import { HttpClient } from "@/lib/api/httpClient";

export abstract class BaseService {
  constructor(protected readonly http: HttpClient) {}
}
