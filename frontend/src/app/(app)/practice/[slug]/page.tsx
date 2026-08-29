import type { Metadata } from "next";
import TopicDetail from "@/components/TopicDetail";

export const metadata: Metadata = { title: "Topic" };

export default async function TopicPage({ params }: { params: Promise<{ slug: string }> }) {
  const { slug } = await params;
  return <TopicDetail slug={slug} />;
}
