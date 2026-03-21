import { NextResponse } from "next/server";

const FASTAPI_URL = process.env.FASTAPI_URL ?? "http://localhost:8000";

export async function GET(): Promise<NextResponse> {
  const res = await fetch(`${FASTAPI_URL}/models`);
  const body = await res.json();
  return NextResponse.json(body, { status: res.status });
}
