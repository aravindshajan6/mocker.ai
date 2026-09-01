import type { Metadata, Viewport } from "next";
import localFont from "next/font/local";
import PwaProvider from "@/components/PwaProvider";
import "./globals.css";

const nunito = localFont({
  src: [
    { path: "../fonts/nunito-latin.woff2", weight: "200 1000", style: "normal" },
    { path: "../fonts/nunito-latin-italic.woff2", weight: "200 1000", style: "italic" },
  ],
  variable: "--font-nunito",
  display: "swap",
});

// Serif italic accent — used for single emphasised words, never body copy.
const fraunces = localFont({
  src: [{ path: "../fonts/fraunces-italic-latin.woff2", weight: "400 700", style: "italic" }],
  variable: "--font-fraunces",
  display: "swap",
});

export const metadata: Metadata = {
  title: { default: "Mocker — one more question", template: "%s · Mocker" },
  description: "Daily GK practice for PSC exams. Calm, fast, and ad-free.",
  applicationName: "Mocker",
  icons: { icon: "/icon.svg", apple: "/icon-192.png" },
  manifest: "/manifest.webmanifest",
  appleWebApp: { capable: true, title: "Mocker", statusBarStyle: "default" },
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
    <html lang="en" className={`${nunito.variable} ${fraunces.variable} h-full antialiased`}>
      <body className="min-h-full flex flex-col">
        {/* First thing in the body so a stored theme is applied before anything is painted;
            a raw <head> element is stripped by the App Router, so it has to live here. */}
        <script
          dangerouslySetInnerHTML={{
            __html: `(function(){try{var t=localStorage.getItem("mocker:theme");if(t==="light"||t==="dark"){document.documentElement.setAttribute("data-theme",t)}}catch(e){}})()`,
          }}
        />
        {children}
        <PwaProvider />
      </body>
    </html>
  );
}
