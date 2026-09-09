import type { Metadata } from "next";
import Landing from "@/components/Landing";

const DESCRIPTION =
  "A calm, ad-free home for Kerala PSC, SSC and UPSC preparation: thousands of exam-style " +
  "questions, real past papers, targeted practice, spaced revision and full-length timed mocks.";

export const metadata: Metadata = {
  title: "Mocker — GK practice for Kerala PSC, SSC and UPSC",
  description: DESCRIPTION,
  alternates: { canonical: "/welcome" },
  openGraph: {
    title: "Mocker — one more question, every single day",
    description: DESCRIPTION,
    type: "website",
    url: "/welcome",
    siteName: "Mocker",
    locale: "en_IN",
    // Absolute at render time via metadataBase in the root layout. Links shared into WhatsApp
    // and Telegram — where most of this audience passes things around — only show a preview
    // image when one is declared with explicit dimensions.
    images: [{ url: "/og.png", width: 1200, height: 630, alt: "Mocker — daily GK practice for PSC exams" }],
  },
  twitter: {
    card: "summary_large_image",
    title: "Mocker — one more question, every single day",
    description: DESCRIPTION,
    images: ["/og.png"],
  },
};

export default function WelcomePage() {
  return <Landing />;
}
