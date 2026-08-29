import type { Metadata } from "next";
import DailyPage from "@/components/DailyPage";

export const metadata: Metadata = { title: "Daily challenge" };

export default function Page() {
  return <DailyPage />;
}
