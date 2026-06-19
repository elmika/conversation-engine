import { NextRequest } from "next/server";
import { proxyJson } from "@/lib/bff";

interface Params {
  params: Promise<{ userId: string; conversationId: string }>;
}

/** POST /api/u/[userId]/conversations/[conversationId]/complete-setup */
export async function POST(_request: NextRequest, { params }: Params) {
  const { userId, conversationId } = await params;
  return proxyJson(`/u/${userId}/conversations/${conversationId}/complete-setup`, { method: "POST" });
}
