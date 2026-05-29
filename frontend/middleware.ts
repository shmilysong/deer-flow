import { NextResponse } from "next/server";
import type { NextRequest } from "next/server";

const PUBLIC_PATHS = ["/_next", "/favicon.ico", "/images", "/ads-login"];

export function middleware(request: NextRequest) {
  const { pathname } = request.nextUrl;

  if (PUBLIC_PATHS.some((p) => pathname.startsWith(p))) {
    return NextResponse.next();
  }

  const adsToken = request.cookies.get("access_token");

  if (pathname === "/") {
    if (adsToken) {
      return NextResponse.redirect(new URL("/workspace", request.url));
    }
    request.nextUrl.pathname = "/ads-login";
    return NextResponse.rewrite(request.nextUrl);
  }

  if (pathname.startsWith("/login")) {
    request.nextUrl.pathname = "/ads-login";
    return NextResponse.rewrite(request.nextUrl);
  }

  if (!adsToken) {
    const loginUrl = new URL("/login", request.url);
    loginUrl.searchParams.set("next", pathname);
    return NextResponse.redirect(loginUrl);
  }

  return NextResponse.next();
}

export const config = {
  matcher: ["/((?!api|_next/static|_next/image|_next/data).*)"],
};
