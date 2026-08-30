// The single low-level HTTP client to the backend REST API.
// Its realtime counterpart is `realtimeClient.ts`.
import { AppConfig } from "@/lib/config";

export class HttpClient {
  constructor(
    private readonly baseUrl: string = AppConfig.apiBase,
    private token: string | null = null,
  ) {}

  setToken(token: string | null) {
    this.token = token;
  }

  async request<T>(path: string, init?: RequestInit): Promise<T> {
    const headers: Record<string, string> = {
      "Content-Type": "application/json",
      ...(init?.headers as Record<string, string> | undefined),
    };
    if (this.token) headers.Authorization = `Bearer ${this.token}`;

    const res = await fetch(`${this.baseUrl}${path}`, {
      ...init,
      headers,
      cache: "no-store",
    });
    if (!res.ok) {
      let detail = res.statusText;
      try {
        const body = await res.json();
        detail = body?.detail || detail;
      } catch {
        // response wasn't JSON — keep statusText
      }
      throw new Error(detail);
    }
    return res.json() as Promise<T>;
  }

  get<T>(path: string): Promise<T> {
    return this.request<T>(path, { method: "GET" });
  }

  post<T>(path: string, body?: unknown): Promise<T> {
    return this.request<T>(path, {
      method: "POST",
      body: body === undefined ? "{}" : JSON.stringify(body),
    });
  }

  patch<T>(path: string, body?: unknown): Promise<T> {
    return this.request<T>(path, {
      method: "PATCH",
      body: body === undefined ? "{}" : JSON.stringify(body),
    });
  }

  put<T>(path: string, body?: unknown): Promise<T> {
    return this.request<T>(path, {
      method: "PUT",
      body: body === undefined ? "{}" : JSON.stringify(body),
    });
  }

  del<T>(path: string): Promise<T> {
    return this.request<T>(path, { method: "DELETE" });
  }
}
