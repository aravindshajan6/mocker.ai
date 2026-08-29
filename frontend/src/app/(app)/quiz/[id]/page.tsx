import type { Metadata } from "next";
import Quiz from "@/components/Quiz";

export const metadata: Metadata = { title: "Quiz" };

export default async function QuizPage({ params }: { params: Promise<{ id: string }> }) {
  const { id } = await params;
  return <Quiz id={id} />;
}
