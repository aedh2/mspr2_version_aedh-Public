import { NextRequest, NextResponse } from "next/server";

const INTERNAL_API_URL = process.env.INTERNAL_API_URL ?? "http://localhost:8000/api";

export async function POST(request: NextRequest) {
  const auth = request.headers.get("authorization") ?? "";
  const body = await request.text();

  const backendResponse = await fetch(`${INTERNAL_API_URL}/ai/recommandations`, {
    method: "POST",
    headers: {
      "Content-Type": "application/json",
      ...(auth ? { authorization: auth } : {})
    },
    body: body || "{}"
  });

  const data = await backendResponse.json();
  return NextResponse.json(data, { status: backendResponse.status });
}
