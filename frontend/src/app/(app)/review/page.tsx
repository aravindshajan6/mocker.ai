import type { Metadata } from "next";
import ReviewPage from "@/components/ReviewPage";

export const metadata: Metadata = { title: "Review" };

export default function Page() {
  return <ReviewPage />;
}
