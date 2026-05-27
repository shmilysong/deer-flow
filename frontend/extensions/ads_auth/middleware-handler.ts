import { NextResponse } from "next/server";
import type { NextRequest } from "next/server";

const PUBLIC_PATHS = ["/_next", "/favicon.ico", "/images", "/ads-login"];

export function middleware(request: NextRequest) {
  const { pathname } = request.nextUrl;

  if (PUBLIC_PATHS.some((p) => pathname.startsWith(p))) {
    return NextResponse.next();
  }

  // 主页用 ADS 登录页替换（URL 地址栏不变）
  if (pathname === "/") {
    request.nextUrl.pathname = "/ads-login";
    return NextResponse.rewrite(request.nextUrl);
  }

  // 所有 /login 路径都用 /ads-login 的内容渲染（URL 地址栏不变）
  if (pathname.startsWith("/login")) {
    request.nextUrl.pathname = "/ads-login";
    return NextResponse.rewrite(request.nextUrl);
  }

  const adsToken = request.cookies.get("ads_token");
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
