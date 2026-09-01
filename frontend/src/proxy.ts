import { NextResponse, type NextRequest } from "next/server";

const PUBLIC = ["/login", "/register", "/offline", "/welcome"];
const COOKIE = "mocker_token";

/**
 * Reads a JWT's `exp` without verifying the signature. The backend is the real authority — this only
 * catches tokens that are structurally broken or plainly expired, so we can clear them before the
 * page loads instead of letting the client bounce between / and /login.
 */
function looksExpired(token: string): boolean {
  const parts = token.split(".");
  if (parts.length !== 3) return true;
  try {
    const payload = JSON.parse(atob(parts[1].replace(/-/g, "+").replace(/_/g, "/")));
    return typeof payload.exp !== "number" || payload.exp * 1000 <= Date.now();
  } catch {
    return true;
  }
}

export function proxy(req: NextRequest) {
  const { pathname } = req.nextUrl;
  const token = req.cookies.get(COOKIE)?.value;
  const isPublic = PUBLIC.some((p) => pathname.startsWith(p));

  if (token && looksExpired(token)) {
    // Stale cookie: send the user to sign-in and drop the cookie so this can't loop.
    const url = req.nextUrl.clone();
    url.pathname = "/login";
    url.search = "";
    const res = isPublic ? NextResponse.next() : NextResponse.redirect(url);
    res.cookies.delete(COOKIE);
    return res;
  }
  if (!token && !isPublic) {
    // A signed-out visitor landing on the root gets the marketing page; a deep link into the
    // app is a returning user, so send those straight to sign-in instead.
    const url = req.nextUrl.clone();
    url.pathname = pathname === "/" ? "/welcome" : "/login";
    url.search = "";
    return NextResponse.redirect(url);
  }
  if (token && isPublic) {
    const url = req.nextUrl.clone();
    url.pathname = "/";
    url.search = "";
    return NextResponse.redirect(url);
  }
  return NextResponse.next();
}

export const config = {
  // Static assets must never be redirected. /sw.js in particular: a redirected service worker
  // fails to register, which silently disables offline support and push notifications.
  matcher: [
    "/((?!api|_next/static|_next/image|sw\\.js|manifest\\.webmanifest|offline|.*\\.(?:png|svg|ico|webmanifest|txt)$).*)",
  ],
};
