// Server-side helper: read the session cookie and build an authenticated
// ApiProvider + current user for server components (pages, layouts).
import { cookies } from "next/headers";
import { createServerApi } from "@/providers/apiProvider";
import type { AuthUser } from "@/models/types";

export async function getServerToken(): Promise<string | null> {
  const jar = await cookies();
  return jar.get("session_token")?.value ?? null;
}

export async function getServerUser(): Promise<AuthUser | null> {
  const token = await getServerToken();
  if (!token) return null;
  try {
    return await createServerApi(token).me();
  } catch {
    return null;
  }
}

export async function getServerApi() {
  const token = await getServerToken();
  return createServerApi(token);
}
