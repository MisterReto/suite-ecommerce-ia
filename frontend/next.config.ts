// Modo standalone/export y proxy al origen API validado; conserva cookies y sirve /login localmente.
// Guía: docs/CODE_GUIDE.md; funciones y objetos: docs/FUNCTION_INDEX.md.
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
  // Public, validated origin used only to wake the free API without proxy headers.
  env: { NEXT_PUBLIC_SUITE_API_ORIGIN: upstream },
  ...(separate ? {
    // Match the API upload allowance plus multipart overhead.
    experimental: { proxyClientMaxBodySize: 13_000_000 },
    async redirects() {
      // Bookmarks open the native workspace; no tool opens a separate legacy page.
      return [
        ["/inventory-hub", "/#inventory/count"], ["/inventory-manager", "/#inventory/count"],
        ["/inventory-count", "/#inventory/count"], ["/inventory-sync", "/#inventory/count"],
        ["/woocommerce-publish-preview", "/#inventory/count"],
        ["/woocommerce-image-preview", "/#more/media"],
        ["/woocommerce-batch-sync", "/#more/publication"],
        ["/woocommerce-product-sync", "/#more/publication"], ["/studio", "/#generate/capture"],
      ].map(([source, destination]) => ({ source, destination, permanent: false }));
    },
    // Sirve /login localmente, dirige /auth/start al login de FastAPI y conserva el proxy de
    // API/callback con el origen validado.
    async rewrites() {
      return { beforeFiles: [
        // Serve the waiting screen locally; issue OAuth state only after API readiness.
        { source: "/login", destination: "/connect-google" },
        { source: "/auth/start", destination: upstream + "/login" },
        ...["/api/:path*", "/auth/:path*", "/suite-static/:path*", "/webhooks/:path*",
            "/logout", "/service-health", "/sync-launch", "/sync-handoff/:path*",
            "/inventory-hub", "/inventory-manager", "/inventory-count", "/inventory-history",
            "/inventory-count-bulk", "/inventory-movement", "/inventory-review",
            "/inventory-sync", "/wc-health", "/wc-preview",
            "/woocommerce-image-preview", "/wp-media-health", "/image-sync-one",
            "/woocommerce-publish-preview", "/stock-preview-start", "/stock-preview-result",
            "/woocommerce-batch-sync", "/batch-create", "/batch-status", "/batch-step", "/batch-resume",
            "/woocommerce-product-sync", "/product-sync-one"]
          .map(source => ({ source, destination: upstream + source })),
      ], afterFiles: [], fallback: [] };
    },
    // Aplica políticas HTTP y no-store al login; la CSP permite únicamente el origen API
    // público configurado para arranque.
    async headers() {
      return [{
        source: "/:path*",
        headers: [
          { key: "X-Content-Type-Options", value: "nosniff" },
          { key: "X-Frame-Options", value: "SAMEORIGIN" },
          { key: "Referrer-Policy", value: "no-referrer" },
          { key: "Permissions-Policy", value: "camera=(self), microphone=(), geolocation=()" },
          { key: "Content-Security-Policy", value: "default-src 'self'; script-src 'self' 'unsafe-inline'; style-src 'self' 'unsafe-inline'; font-src 'self' data:; img-src 'self' data: blob: https:; connect-src 'self' " + upstream + "; worker-src 'self' blob:; frame-ancestors 'self'; object-src 'none'; base-uri 'self'; form-action 'self'" },
        ],
      }, ...["/login", "/connect-google"].map(source => ({
        source,
        headers: [{ key: "Cache-Control", value: "no-store" }],
      }))];
    },
  } : {}),
};
export default config;
