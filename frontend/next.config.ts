import type { NextConfig } from "next";

const separate = process.env.SUITE_FRONTEND_MODE === "standalone";
let upstream = "";
if (separate) {
  const url = new URL(process.env.SUITE_API_ORIGIN || "");
  if (url.protocol !== "https:" || url.username || url.password ||
      url.search || url.hash || url.pathname !== "/") {
    throw new Error("SUITE_API_ORIGIN must be the HTTPS API origin without credentials or a path.");
  }
  upstream = url.origin;
}

const config: NextConfig = {
  output: separate ? "standalone" : "export",
  trailingSlash: !separate,
  skipTrailingSlashRedirect: separate,
  images: { unoptimized: true },
  devIndicators: false,
  poweredByHeader: false,
  ...(separate ? {
    async rewrites() {
      return { beforeFiles: [
        ...["/api/:path*", "/auth/:path*", "/suite-static/:path*", "/webhooks/:path*",
            "/login", "/logout", "/service-health", "/sync-connect", "/sync-handoff/:path*"]
          .map(source => ({ source, destination: upstream + source })),
      ], afterFiles: [], fallback: [] };
    },
    async headers() {
      return [{
        source: "/:path*",
        headers: [
          { key: "X-Content-Type-Options", value: "nosniff" },
          { key: "X-Frame-Options", value: "SAMEORIGIN" },
          { key: "Referrer-Policy", value: "no-referrer" },
          { key: "Permissions-Policy", value: "camera=(self), microphone=(), geolocation=()" },
          { key: "Content-Security-Policy", value: "default-src 'self'; script-src 'self' 'unsafe-inline'; style-src 'self' 'unsafe-inline'; font-src 'self' data:; img-src 'self' data: blob: https:; connect-src 'self'; worker-src 'self' blob:; frame-ancestors 'self'; object-src 'none'; base-uri 'self'; form-action 'self'" },
        ],
      }];
    },
  } : {}),
};
export default config;
