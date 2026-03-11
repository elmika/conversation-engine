import { NextRequest, NextResponse } from "next/server";

const FASTAPI_URL = process.env.FASTAPI_URL ?? "http://localhost:8000";

/** PATCH /api/conversations/[conversationId] — rename conversation */
export async function PATCH(
  request: NextRequest,
  { params }: { params: Promise<{ conversationId: string }> }
): Promise<NextResponse> {
  const { conversationId } = await params;
  const res = await fetch(`${FASTAPI_URL}/conversations/${conversationId}`, {
    method: "PATCH",
    headers: { "Content-Type": "application/json" },
    body: await request.text(),
  });
  const body = await res.json();
  return NextResponse.json(body, { status: res.status });
}

/** POST /api/conversations/[conversationId] — append turn (non-streaming) */
export async function POST(
  request: NextRequest,
  { params }: { params: Promise<{ conversationId: string }> }
): Promise<NextResponse> {
  const { conversationId } = await params;
  const res = await fetch(`${FASTAPI_URL}/conversations/${conversationId}`, {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: await request.text(),
  });
  const body = await res.json();
  return NextResponse.json(body, { status: res.status });
}
