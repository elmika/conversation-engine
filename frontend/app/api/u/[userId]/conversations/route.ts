import { NextRequest, NextResponse } from "next/server";

const FASTAPI_URL = process.env.FASTAPI_URL ?? "http://localhost:8000";

interface Params {
  params: Promise<{ userId: string }>;
}

/** GET /api/u/[userId]/conversations?page=&page_size= — list conversations */
export async function GET(request: NextRequest, { params }: Params): Promise<NextResponse> {
  const { userId } = await params;
  const { searchParams } = request.nextUrl;
  const page = searchParams.get("page") ?? "1";
  const pageSize = searchParams.get("page_size") ?? "20";

  const res = await fetch(
    `${FASTAPI_URL}/u/${userId}/conversations?page=${page}&page_size=${pageSize}`
  );
  const body = await res.json();
  return NextResponse.json(body, { status: res.status });
}

/** POST /api/u/[userId]/conversations — create conversation (non-streaming) */
export async function POST(request: NextRequest, { params }: Params): Promise<NextResponse> {
  const { userId } = await params;
  const res = await fetch(`${FASTAPI_URL}/u/${userId}/conversations`, {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: await request.text(),
  });
  const body = await res.json();
  return NextResponse.json(body, { status: res.status });
}
