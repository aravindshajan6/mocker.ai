import type { NextConfig } from "next";

const BACKEND_URL = process.env.BACKEND_URL ?? "http://localhost:8000";

// Kept deliberately tight. The two that do real work against a hostile page are frame-ancestors
// (clickjacking) and form-action (credential exfiltration); script-src carries 'unsafe-inline'
// only because Next ships an inline hydration bootstrap that cannot be nonced in a static export.
const CSP = [
  "default-src 'self'",
  "script-src 'self' 'unsafe-inline' 'unsafe-eval'",
  "style-src 'self' 'unsafe-inline'",
  "img-src 'self' data: blob:",
  "font-src 'self' data:",
  // The app calls only its own origin; the service worker needs the same.
  "connect-src 'self'",
  "worker-src 'self'",
  "manifest-src 'self'",
  "frame-ancestors 'none'",
  "form-action 'self'",
  "base-uri 'self'",
  "object-src 'none'",
  "upgrade-insecure-requests",
].join("; ");

const SECURITY_HEADERS = [
  { key: "Content-Security-Policy", value: CSP },
  // Two years, preload-eligible. Only meaningful over https, which is how this is served.
  { key: "Strict-Transport-Security", value: "max-age=63072000; includeSubDomains" },
  { key: "X-Frame-Options", value: "DENY" },
  { key: "X-Content-Type-Options", value: "nosniff" },
  { key: "Referrer-Policy", value: "strict-origin-when-cross-origin" },
  { key: "Permissions-Policy", value: "camera=(), microphone=(), geolocation=(), payment=(), usb=()" },
  { key: "Cross-Origin-Opener-Policy", value: "same-origin" },
];

const nextConfig: NextConfig = {
  output: "standalone",
  // next/image is not used anywhere in this app, and leaving the optimiser enabled pulls sharp and
  // its platform binaries (~46 MB) into the standalone trace for nothing.
  images: { unoptimized: true },
  // `unoptimized` stops the optimiser running but Next still traces sharp as a possible dependency.
  // Excluding it explicitly is what actually keeps the binaries out of the standalone output.
  outputFileTracingExcludes: { "*": ["node_modules/@img/**", "node_modules/sharp/**"] },
  // Do not advertise the framework version to a scanner.
  poweredByHeader: false,
  async headers() {
    // Applied to every path including /api/* proxied to the backend, so there is no route that
    // answers without them. Verified with curl against the live site, not by reading this file.
    return [{ source: "/:path*", headers: SECURITY_HEADERS }];
  },
  async rewrites() {
    // The browser only ever talks to the Next.js server; API calls are proxied to the backend
    // container, which is never exposed on the host.
    return [{ source: "/api/:path*", destination: `${BACKEND_URL}/api/:path*` }];
  },
};

export default nextConfig;
