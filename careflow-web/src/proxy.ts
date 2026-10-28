import { createHash, timingSafeEqual } from "node:crypto";
import { NextResponse, type NextRequest } from "next/server";

function secureMatch(actual: string, expected: string): boolean {
  const digest = (value: string) =>
    createHash("sha256").update(value).digest();

  return timingSafeEqual(digest(actual), digest(expected));
}

function unauthorized(): Response {
  return new Response("Authentication required", {
    status: 401,
    headers: {
      "WWW-Authenticate": 'Basic realm="CareFlow"',
      "Cache-Control": "no-store",
    },
  });
}

export function proxy(request: NextRequest) {
  const expectedUser = process.env.CAREFLOW_ACCESS_USER;
  const expectedPassword = process.env.CAREFLOW_ACCESS_PASSWORD;

  // Fail closed if credentials are not configured.
  if (!expectedUser || !expectedPassword) {
    return new Response("Access configuration unavailable", {
      status: 503,
      headers: { "Cache-Control": "no-store" },
    });
  }

  const authorization = request.headers.get("authorization");

  if (!authorization?.startsWith("Basic ")) {
    return unauthorized();
  }

  const decoded = Buffer.from(
    authorization.slice(6),
    "base64"
  ).toString("utf8");

  const separator = decoded.indexOf(":");

  if (separator < 0) {
    return unauthorized();
  }

  const username = decoded.slice(0, separator);
  const password = decoded.slice(separator + 1);

  if (
    !secureMatch(username, expectedUser) ||
    !secureMatch(password, expectedPassword)
  ) {
    return unauthorized();
  }

  return NextResponse.next();
}

export const config = {
  matcher: [
    "/",
    "/api/snowflake/:path*",
  ],
};
