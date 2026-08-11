import type { Metadata } from "next";
import "./globals.css";
import "./enhancements.css";

export const metadata: Metadata = {
  title: "Optika OS",
  description: "Optika biznesini boshqarish tizimi",
  manifest: "/manifest.webmanifest",
  applicationName: "Optika OS",
  appleWebApp: { capable: true, title: "Optika OS", statusBarStyle: "default" },
};

export default function RootLayout({ children }: Readonly<{ children: React.ReactNode }>) {
  return (
    <html lang="uz">
      <body>{children}</body>
    </html>
  );
}
