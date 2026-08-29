import type { Metadata } from "next";
import ExamStart from "@/components/ExamStart";

export const metadata: Metadata = { title: "Exam mode" };

export default function ExamPage() {
  return <ExamStart />;
}
