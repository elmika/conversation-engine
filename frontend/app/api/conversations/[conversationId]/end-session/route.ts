import { NextRequest, NextResponse } from "next/server";

const FASTAPI_URL = process.env.FASTAPI_URL ?? "http://localhost:8000";

/** POST /api/conversations/[conversationId]/end-session — end a conversation session */
export async function POST(
  _request: NextRequest,
  { params }: { params: Promise<{ conversationId: string }> }
): Promise<NextResponse> {
  const { conversationId } = await params;
  const res = await fetch(
    `${FASTAPI_URL}/conversations/${conversationId}/end-session`,
    { method: "POST" }
  );
  const body = await res.json();
  return NextResponse.json(body, { status: res.status });
}
