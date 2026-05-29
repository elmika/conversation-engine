import { NextRequest, NextResponse } from "next/server";

const FASTAPI_URL = process.env.FASTAPI_URL ?? "http://localhost:8000";

interface Params {
  params: Promise<{ userId: string; conversationId: string }>;
}

/** POST /api/u/[userId]/conversations/[conversationId] — append turn (non-streaming) */
export async function POST(request: NextRequest, { params }: Params): Promise<NextResponse> {
  const { userId, conversationId } = await params;
  const res = await fetch(`${FASTAPI_URL}/u/${userId}/conversations/${conversationId}`, {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: await request.text(),
  });
  const body = await res.json();
  return NextResponse.json(body, { status: res.status });
}

/** PATCH /api/u/[userId]/conversations/[conversationId] — rename conversation */
export async function PATCH(request: NextRequest, { params }: Params): Promise<NextResponse> {
  const { userId, conversationId } = await params;
  const res = await fetch(`${FASTAPI_URL}/u/${userId}/conversations/${conversationId}`, {
    method: "PATCH",
    headers: { "Content-Type": "application/json" },
    body: await request.text(),
  });
  const body = await res.json();
  return NextResponse.json(body, { status: res.status });
}

/** DELETE /api/u/[userId]/conversations/[conversationId] — delete conversation */
export async function DELETE(_request: NextRequest, { params }: Params): Promise<NextResponse> {
  const { userId, conversationId } = await params;
  const res = await fetch(`${FASTAPI_URL}/u/${userId}/conversations/${conversationId}`, {
    method: "DELETE",
  });
  if (res.status === 204) return new NextResponse(null, { status: 204 });
  const body = await res.json();
  return NextResponse.json(body, { status: res.status });
}
