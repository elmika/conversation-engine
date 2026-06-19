import { NextRequest, NextResponse } from "next/server";

const FASTAPI_URL = process.env.FASTAPI_URL ?? "http://localhost:8000";

interface Params {
  params: Promise<{ userId: string; conversationId: string }>;
}

/** POST /api/u/[userId]/conversations/[conversationId]/complete-setup */
export async function POST(_request: NextRequest, { params }: Params): Promise<NextResponse> {
  const { userId, conversationId } = await params;
  const res = await fetch(
    `${FASTAPI_URL}/u/${userId}/conversations/${conversationId}/complete-setup`,
    { method: "POST" }
  );
  const body = await res.json();
  return NextResponse.json(body, { status: res.status });
}
