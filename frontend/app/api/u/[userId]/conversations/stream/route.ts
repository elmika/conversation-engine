import { NextRequest } from "next/server";
import { jsonBody, proxyStream } from "@/lib/bff";

interface Params {
  params: Promise<{ userId: string }>;
}

/** POST /api/u/[userId]/conversations/stream — create conversation with SSE streaming */
export async function POST(request: NextRequest, { params }: Params) {
  const { userId } = await params;
  return proxyStream(`/u/${userId}/conversations/stream`, await jsonBody(request, "POST"));
}
