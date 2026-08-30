import type { Metadata } from "next";
import AnswersPage from "@/components/AnswersPage";

export const metadata: Metadata = { title: "My answers" };

export default function Page() {
  return <AnswersPage />;
}
