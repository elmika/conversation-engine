import { NextRequest } from "next/server";
import { proxyJson } from "@/lib/bff";

interface Params {
  params: Promise<{ userId: string }>;
}

/** GET /api/u/[userId]/status — check if learner profile exists */
export async function GET(_request: NextRequest, { params }: Params) {
  const { userId } = await params;
  return proxyJson(`/u/${userId}/status`);
}
