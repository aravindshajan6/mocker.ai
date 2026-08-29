import type { Metadata } from "next";
import Exam from "@/components/Exam";

export const metadata: Metadata = { title: "Exam in progress" };

export default async function ExamRunPage({ params }: { params: Promise<{ id: string }> }) {
  const { id } = await params;
  return <Exam id={id} />;
}
