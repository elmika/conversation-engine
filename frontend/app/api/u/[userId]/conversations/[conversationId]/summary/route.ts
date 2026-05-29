import { NextRequest, NextResponse } from "next/server";

const FASTAPI_URL = process.env.FASTAPI_URL ?? "http://localhost:8000";

interface Params {
  params: Promise<{ userId: string; conversationId: string }>;
}

/** GET /api/u/[userId]/conversations/[conversationId]/summary */
export async function GET(_request: NextRequest, { params }: Params): Promise<NextResponse> {
  const { userId, conversationId } = await params;
  const res = await fetch(
    `${FASTAPI_URL}/u/${userId}/conversations/${conversationId}/summary`
  );
  const body = await res.json();
  return NextResponse.json(body, { status: res.status });
}
