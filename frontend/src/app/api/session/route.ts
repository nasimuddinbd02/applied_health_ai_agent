// Sets/clears the httpOnly session cookie so server components can read the
// logged-in user's token (client-side state alone can't be read during SSR).
import { cookies } from "next/headers";
import { NextRequest, NextResponse } from "next/server";

const COOKIE = "session_token";

export async function POST(req: NextRequest) {
  const { token } = await req.json();
  const jar = await cookies();
  jar.set(COOKIE, token, {
    httpOnly: true,
    sameSite: "lax",
    path: "/",
    maxAge: 60 * 60 * 12,
  });
  return NextResponse.json({ ok: true });
}

export async function DELETE() {
  const jar = await cookies();
  jar.delete(COOKIE);
  return NextResponse.json({ ok: true });
}
