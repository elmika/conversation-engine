import { NextRequest, NextResponse } from "next/server";

const FASTAPI_URL = process.env.FASTAPI_URL ?? "http://localhost:8000";

/** POST /api/conversations/[conversationId]/rewind/stream — rewind + re-stream with SSE */
export async function POST(
  request: NextRequest,
  { params }: { params: Promise<{ conversationId: string }> }
): Promise<Response> {
  const { conversationId } = await params;
  const upstream = await fetch(
    `${FASTAPI_URL}/conversations/${conversationId}/rewind/stream`,
    {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: await request.text(),
    }
  );

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
