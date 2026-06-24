import { NextRequest } from "next/server";
import { jsonBody, proxyJson } from "@/lib/bff";

interface Params {
  params: Promise<{ userId: string }>;
}

/** GET /api/u/[userId]/conversations?page=&page_size= — list conversations */
export async function GET(request: NextRequest, { params }: Params) {
  const { userId } = await params;
  const { searchParams } = request.nextUrl;
  const page = searchParams.get("page") ?? "1";
  const pageSize = searchParams.get("page_size") ?? "20";
  return proxyJson(`/u/${userId}/conversations?page=${page}&page_size=${pageSize}`);
}

/** POST /api/u/[userId]/conversations — create conversation (non-streaming) */
export async function POST(request: NextRequest, { params }: Params) {
  const { userId } = await params;
  return proxyJson(`/u/${userId}/conversations`, await jsonBody(request, "POST"));
}
