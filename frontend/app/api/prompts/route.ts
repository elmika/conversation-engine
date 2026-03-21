import { NextRequest, NextResponse } from "next/server";

const FASTAPI_URL = process.env.FASTAPI_URL ?? "http://localhost:8000";

export async function GET(request: NextRequest): Promise<NextResponse> {
  const all = request.nextUrl.searchParams.get("all");
  const url = all === "true"
    ? `${FASTAPI_URL}/prompts?all=true`
    : `${FASTAPI_URL}/prompts`;
  const res = await fetch(url);
  const body = await res.json();
  return NextResponse.json(body, { status: res.status });
}

export async function POST(request: NextRequest): Promise<NextResponse> {
  const body = await request.json();
  const res = await fetch(`${FASTAPI_URL}/prompts`, {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify(body),
  });
  const data = await res.json();
  return NextResponse.json(data, { status: res.status });
}
