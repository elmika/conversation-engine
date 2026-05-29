import { NextRequest, NextResponse } from "next/server";

const FASTAPI_URL = process.env.FASTAPI_URL ?? "http://localhost:8000";

interface Params {
  params: Promise<{ userId: string }>;
}

/** GET /api/u/[userId]/status — check if learner profile exists */
export async function GET(_request: NextRequest, { params }: Params): Promise<NextResponse> {
  const { userId } = await params;
  const res = await fetch(`${FASTAPI_URL}/u/${userId}/status`);
  const body = await res.json();
  return NextResponse.json(body, { status: res.status });
}
