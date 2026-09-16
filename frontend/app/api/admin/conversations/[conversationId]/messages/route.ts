import { NextRequest, NextResponse } from "next/server";
import { proxyJson, authOnly } from "@/lib/bff";

interface Params {
  params: Promise<{ conversationId: string }>;
}

/** GET /api/admin/conversations/[conversationId]/messages */
export async function GET(request: NextRequest, { params }: Params): Promise<NextResponse> {
  const { conversationId } = await params;
  return proxyJson(`/admin/conversations/${conversationId}/messages`, authOnly(request, "GET"));
}
