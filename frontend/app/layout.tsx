import type { Metadata, Viewport } from "next";
import "@fontsource/poppins/400.css";
import "@fontsource/poppins/500.css";
import "@fontsource/poppins/600.css";
import "@fontsource/poppins/700.css";
import "./globals.css";

export const metadata: Metadata = {
  title: "Suite e-commerce · El Rincón de Asia",
  description:
    "El estudio de productos, imágenes e inventario de El Rincón de Asia.",
  icons: { icon: "/logo.png", apple: "/icons/icon-192.png" },
  manifest: "/manifest.webmanifest",
  appleWebApp: { capable: true, statusBarStyle: "default", title: "Rincón IA" },
  robots: { index: false, follow: false },
};

export const viewport: Viewport = { themeColor: "#f60813", width: "device-width", initialScale: 1, viewportFit: "cover" };

export default function RootLayout({
  children,
}: Readonly<{ children: React.ReactNode }>) {
  return (
    <html lang="es">
      <body>{children}</body>
    </html>
  );
}
