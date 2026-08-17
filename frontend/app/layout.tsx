import type { Metadata, Viewport } from "next";
import "./globals.css";
import "./enhancements.css";

export const metadata: Metadata = {
  title: "Optika OS",
  description: "Optika biznesini boshqarish tizimi",
  manifest: "/manifest.webmanifest",
  applicationName: "Optika OS",
  icons: {
    icon: [
      { url: "/favicon-32.png", sizes: "32x32", type: "image/png" },
      { url: "/icon-192.png", sizes: "192x192", type: "image/png" },
      { url: "/optika-icon.svg", type: "image/svg+xml" },
    ],
    apple: [{ url: "/apple-touch-icon.png", sizes: "180x180", type: "image/png" }],
  },
  appleWebApp: { capable: true, title: "Optika OS", statusBarStyle: "default" },
};

export const viewport: Viewport = {
  themeColor: "#087653",
  width: "device-width",
  initialScale: 1,
  viewportFit: "cover",
};

export default function RootLayout({ children }: Readonly<{ children: React.ReactNode }>) {
  return (
    <html lang="uz">
      <body>{children}</body>
    </html>
  );
}
