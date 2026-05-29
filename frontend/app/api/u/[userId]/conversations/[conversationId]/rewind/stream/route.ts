import { NextRequest, NextResponse } from "next/server";

const FASTAPI_URL = process.env.FASTAPI_URL ?? "http://localhost:8000";

interface Params {
  params: Promise<{ userId: string; conversationId: string }>;
}

/** POST /api/u/[userId]/conversations/[conversationId]/rewind/stream — rewind + stream */
export async function POST(request: NextRequest, { params }: Params): Promise<Response> {
  const { userId, conversationId } = await params;
  const upstream = await fetch(
    `${FASTAPI_URL}/u/${userId}/conversations/${conversationId}/rewind/stream`,
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
