import { NextRequest, NextResponse } from "next/server";
import { proxyJson, jsonBody } from "@/lib/bff";

export async function GET(request: NextRequest): Promise<NextResponse> {
  const all = request.nextUrl.searchParams.get("all");
  const path = all === "true" ? "/prompts?all=true" : "/prompts";
  return proxyJson(path);
}

export async function POST(request: NextRequest): Promise<NextResponse> {
  return proxyJson("/prompts", await jsonBody(request, "POST"));
}
