import type { Metadata } from "next";
import AnswerReview from "@/components/AnswerReview";

export const metadata: Metadata = { title: "Review answers" };

export default async function Page({ params }: { params: Promise<{ id: string }> }) {
  const { id } = await params;
  return <AnswerReview id={id} />;
}
