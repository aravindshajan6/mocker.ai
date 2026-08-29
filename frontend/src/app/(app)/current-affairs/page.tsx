import type { Metadata } from "next";
import CurrentAffairsPage from "@/components/CurrentAffairsPage";

export const metadata: Metadata = { title: "Current affairs" };

export default function Page() {
  return <CurrentAffairsPage />;
}
