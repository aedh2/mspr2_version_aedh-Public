import { NextRequest, NextResponse } from "next/server";

const INTERNAL_API_URL = process.env.INTERNAL_API_URL ?? "http://localhost:8000/api";

export async function POST(request: NextRequest) {
  const formData = await request.formData();
  const auth = request.headers.get("authorization") ?? request.headers.get("Authorization") ?? "";

  const backendResponse = await fetch(`${INTERNAL_API_URL}/ai/analyse-repas`, {
    method: "POST",
    headers: auth ? { authorization: auth } : {},
    body: formData
  });

  const data = await backendResponse.json();
  return NextResponse.json(data, { status: backendResponse.status });
}
