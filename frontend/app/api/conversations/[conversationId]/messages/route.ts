import { NextRequest, NextResponse } from "next/server";

const FASTAPI_URL = process.env.FASTAPI_URL ?? "http://localhost:8000";

/** GET /api/conversations/[conversationId]/messages */
export async function GET(
  _request: NextRequest,
  { params }: { params: Promise<{ conversationId: string }> }
): Promise<NextResponse> {
  const { conversationId } = await params;
  const res = await fetch(
    `${FASTAPI_URL}/conversations/${conversationId}/messages`
  );
  const body = await res.json();
  return NextResponse.json(body, { status: res.status });
}
