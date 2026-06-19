import { NextRequest } from "next/server";
import { proxyJson } from "@/lib/bff";

interface Params {
  params: Promise<{ userId: string; conversationId: string }>;
}

/** GET /api/u/[userId]/conversations/[conversationId]/messages */
export async function GET(_request: NextRequest, { params }: Params) {
  const { userId, conversationId } = await params;
  return proxyJson(`/u/${userId}/conversations/${conversationId}/messages`);
}
