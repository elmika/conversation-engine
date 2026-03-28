import { NextRequest, NextResponse } from "next/server";

const FASTAPI_URL = process.env.FASTAPI_URL ?? "http://localhost:8000";

export async function GET(
  request: NextRequest,
  { params }: { params: Promise<{ slug: string }> }
): Promise<NextResponse> {
  const { slug } = await params;
  const { searchParams } = request.nextUrl;
  const conversationId = searchParams.get("conversation_id");
  const url = conversationId
    ? `${FASTAPI_URL}/prompts/${slug}/render?conversation_id=${conversationId}`
    : `${FASTAPI_URL}/prompts/${slug}/render`;
  const res = await fetch(url);
  const data = await res.json();
  return NextResponse.json(data, { status: res.status });
}
