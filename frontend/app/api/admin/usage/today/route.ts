import { NextRequest, NextResponse } from "next/server";
import { proxyJson, authOnly } from "@/lib/bff";

export async function GET(request: NextRequest): Promise<NextResponse> {
  return proxyJson("/admin/usage/today", authOnly(request, "GET"));
}
