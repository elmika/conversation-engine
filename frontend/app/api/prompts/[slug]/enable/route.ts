import { NextRequest, NextResponse } from "next/server";
import { proxyJson, authOnly } from "@/lib/bff";

export async function PATCH(
  request: NextRequest,
  { params }: { params: Promise<{ slug: string }> }
): Promise<NextResponse> {
  const { slug } = await params;
  return proxyJson(`/prompts/${slug}/enable`, authOnly(request, "PATCH"));
}
