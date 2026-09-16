import { NextRequest, NextResponse } from "next/server";
import { proxyJson, jsonBody, authOnly } from "@/lib/bff";

export async function PUT(
  request: NextRequest,
  { params }: { params: Promise<{ slug: string }> }
): Promise<NextResponse> {
  const { slug } = await params;
  return proxyJson(`/prompts/${slug}`, await jsonBody(request, "PUT"));
}

export async function DELETE(
  request: NextRequest,
  { params }: { params: Promise<{ slug: string }> }
): Promise<NextResponse> {
  const { slug } = await params;
  return proxyJson(`/prompts/${slug}`, authOnly(request, "DELETE"));
}
