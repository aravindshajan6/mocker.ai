import type { Metadata } from "next";
import Landing from "@/components/Landing";

export const metadata: Metadata = {
  title: "Mocker — daily GK practice for PSC exams",
  description:
    "A calm, ad-free way to build General Knowledge for Kerala PSC, SSC and UPSC. Ten questions a day, spaced revision, timed mock papers, and current affairs from the morning's news.",
  openGraph: {
    title: "Mocker — one more question",
    description: "Daily GK practice for Kerala PSC, SSC and UPSC. Calm, fast, and ad-free.",
    type: "website",
  },
};

export default function WelcomePage() {
  return <Landing />;
}
