import type { Metadata } from "next";
import Practice from "@/components/Practice";

export const metadata: Metadata = { title: "Topics" };

export default function PracticePage() {
  return <Practice />;
}
