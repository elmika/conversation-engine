import { NextRequest, NextResponse } from "next/server";

const FASTAPI_URL = process.env.FASTAPI_URL ?? "http://localhost:8000";

export async function PATCH(
  _request: NextRequest,
  { params }: { params: Promise<{ slug: string }> }
): Promise<NextResponse> {
  const { slug } = await params;
  const res = await fetch(`${FASTAPI_URL}/prompts/${slug}/disable`, { method: "PATCH" });
  const data = await res.json();
  return NextResponse.json(data, { status: res.status });
}
