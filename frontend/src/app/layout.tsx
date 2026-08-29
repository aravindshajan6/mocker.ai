import type { Metadata, Viewport } from "next";
import localFont from "next/font/local";
import "./globals.css";

const nunito = localFont({
  src: [
    { path: "../fonts/nunito-latin.woff2", weight: "200 1000", style: "normal" },
    { path: "../fonts/nunito-latin-italic.woff2", weight: "200 1000", style: "italic" },
  ],
  variable: "--font-nunito",
  display: "swap",
});

export const metadata: Metadata = {
  title: { default: "Mocker — one more question", template: "%s · Mocker" },
  description: "Daily GK practice for PSC exams. Calm, fast, and ad-free.",
  applicationName: "Mocker",
  icons: { icon: "/icon.svg" },
};

export const viewport: Viewport = {
  themeColor: [
    { media: "(prefers-color-scheme: light)", color: "#fbf7f0" },
    { media: "(prefers-color-scheme: dark)", color: "#131a21" },
  ],
  width: "device-width",
  initialScale: 1,
  viewportFit: "cover",
};

export default function RootLayout({ children }: { children: React.ReactNode }) {
  return (
    <html lang="en" className={`${nunito.variable} h-full antialiased`}>
      <body className="min-h-full flex flex-col">{children}</body>
    </html>
  );
}
