import type { Metadata } from "next";
import Result from "@/components/Result";

export const metadata: Metadata = { title: "Results" };

export default async function ResultPage({ params }: { params: Promise<{ id: string }> }) {
  const { id } = await params;
  return <Result id={id} />;
}
