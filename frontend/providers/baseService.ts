// Base class for the feature service classes — holds the HTTP client.
import { HttpClient } from "@/dbacces/httpClient";

export abstract class BaseService {
  constructor(protected readonly http: HttpClient) {}
}
