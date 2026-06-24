/**
 * Server-only BFF (Backend-for-Frontend) proxy helpers.
 *
 * Every Route Handler forwards to FastAPI with one of two shapes — a JSON
 * round-trip or an SSE stream pipe — plus the same upstream URL and headers.
 * These helpers hold that one copy so the route files stay one-liners and the
 * FastAPI URL is never duplicated (or leaked to the browser).
 *
 * Do NOT import this from a Client Component — it reads process.env and uses
 * next/server.
 */

import { NextRequest, NextResponse } from "next/server";

export const FASTAPI_URL = process.env.FASTAPI_URL ?? "http://localhost:8000";

/** RequestInit for a body-carrying JSON request, forwarding the incoming body verbatim. */
export async function jsonBody(request: NextRequest, method: string): Promise<RequestInit> {
  return {
    method,
    headers: { "Content-Type": "application/json" },
    body: await request.text(),
  };
}

/**
 * Proxy a JSON request to FastAPI: forward to `path`, return the JSON body with
 * the upstream status. Handles 204 No Content (no body to parse).
 */
export async function proxyJson(path: string, init?: RequestInit): Promise<NextResponse> {
  const res = await fetch(`${FASTAPI_URL}${path}`, init);
  if (res.status === 204) return new NextResponse(null, { status: 204 });
  const body = await res.json();
  return NextResponse.json(body, { status: res.status });
}

/**
 * Proxy an SSE request to FastAPI: pipe the event stream through unbuffered, or
 * return the JSON error body on a non-OK upstream so the client sees the failure.
 */
export async function proxyStream(path: string, init?: RequestInit): Promise<Response> {
  const upstream = await fetch(`${FASTAPI_URL}${path}`, init);
  if (!upstream.ok) {
    const body = await upstream.json().catch(() => ({ detail: upstream.statusText }));
    return NextResponse.json(body, { status: upstream.status });
  }
  return new Response(upstream.body, {
    headers: {
      "Content-Type": "text/event-stream",
      "Cache-Control": "no-cache",
      "X-Accel-Buffering": "no",
    },
  });
}
