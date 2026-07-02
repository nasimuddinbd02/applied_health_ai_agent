// Cross-cutting frontend config / constants.
export class AppConfig {
  static readonly apiBase: string =
    process.env.NEXT_PUBLIC_API_BASE || "http://localhost:8000";
}
