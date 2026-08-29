import type { Metadata } from "next";
import HistoryPage from "@/components/HistoryPage";

export const metadata: Metadata = { title: "History" };

export default function Page() {
  return <HistoryPage />;
}
