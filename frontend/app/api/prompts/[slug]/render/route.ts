import { NextRequest, NextResponse } from "next/server";
import { proxyJson, authOnly } from "@/lib/bff";

export async function GET(
  request: NextRequest,
  { params }: { params: Promise<{ slug: string }> }
): Promise<NextResponse> {
  const { slug } = await params;
  const conversationId = request.nextUrl.searchParams.get("conversation_id");
  const path = conversationId
    ? `/prompts/${slug}/render?conversation_id=${conversationId}`
    : `/prompts/${slug}/render`;
  return proxyJson(path, authOnly(request, "GET"));
}
