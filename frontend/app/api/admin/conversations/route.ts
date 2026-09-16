import { NextRequest, NextResponse } from "next/server";
import { proxyJson, authOnly } from "@/lib/bff";

export async function GET(request: NextRequest): Promise<NextResponse> {
  const { searchParams } = request.nextUrl;
  const qs = searchParams.toString();
  return proxyJson(`/admin/conversations${qs ? `?${qs}` : ""}`, authOnly(request, "GET"));
}
