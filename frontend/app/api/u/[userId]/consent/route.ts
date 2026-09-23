import { NextRequest } from "next/server";
import { proxyJson } from "@/lib/bff";

interface Params {
  params: Promise<{ userId: string }>;
}

/** GET /api/u/[userId]/consent — check whether this learner has a recorded consent record */
export async function GET(_request: NextRequest, { params }: Params) {
  const { userId } = await params;
  return proxyJson(`/u/${userId}/consent`);
}

/** POST /api/u/[userId]/consent — record consent for this learner */
export async function POST(_request: NextRequest, { params }: Params) {
  const { userId } = await params;
  return proxyJson(`/u/${userId}/consent`, { method: "POST" });
}
