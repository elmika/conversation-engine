import { NextRequest } from "next/server";
import { jsonBody, proxyJson } from "@/lib/bff";

interface Params {
  params: Promise<{ userId: string; conversationId: string }>;
}

/** POST /api/u/[userId]/conversations/[conversationId] — append turn (non-streaming) */
export async function POST(request: NextRequest, { params }: Params) {
  const { userId, conversationId } = await params;
  return proxyJson(`/u/${userId}/conversations/${conversationId}`, await jsonBody(request, "POST"));
}

/** PATCH /api/u/[userId]/conversations/[conversationId] — rename conversation */
export async function PATCH(request: NextRequest, { params }: Params) {
  const { userId, conversationId } = await params;
  return proxyJson(`/u/${userId}/conversations/${conversationId}`, await jsonBody(request, "PATCH"));
}

/** DELETE /api/u/[userId]/conversations/[conversationId] — delete conversation */
export async function DELETE(_request: NextRequest, { params }: Params) {
  const { userId, conversationId } = await params;
  return proxyJson(`/u/${userId}/conversations/${conversationId}`, { method: "DELETE" });
}
