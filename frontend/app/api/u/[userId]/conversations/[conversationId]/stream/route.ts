import { NextRequest } from "next/server";
import { jsonBody, proxyStream } from "@/lib/bff";

interface Params {
  params: Promise<{ userId: string; conversationId: string }>;
}

/** POST /api/u/[userId]/conversations/[conversationId]/stream — append turn with SSE */
export async function POST(request: NextRequest, { params }: Params) {
  const { userId, conversationId } = await params;
  return proxyStream(
    `/u/${userId}/conversations/${conversationId}/stream`,
    await jsonBody(request, "POST")
  );
}
