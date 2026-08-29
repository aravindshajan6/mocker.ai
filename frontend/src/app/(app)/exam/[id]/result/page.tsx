import type { Metadata } from "next";
import ExamResult from "@/components/ExamResult";

export const metadata: Metadata = { title: "Exam result" };

export default async function ExamResultPage({ params }: { params: Promise<{ id: string }> }) {
  const { id } = await params;
  return <ExamResult id={id} />;
}
