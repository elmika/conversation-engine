import { NextRequest } from "next/server";
import { jsonBody, proxyStream } from "@/lib/bff";

interface Params {
  params: Promise<{ userId: string }>;
}

/** POST /api/u/[userId]/conversations/init-stream — AI-initiated opening message */
export async function POST(request: NextRequest, { params }: Params) {
  const { userId } = await params;
  return proxyStream(`/u/${userId}/conversations/init-stream`, await jsonBody(request, "POST"));
}
