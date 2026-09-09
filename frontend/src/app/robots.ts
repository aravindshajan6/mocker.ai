import type { MetadataRoute } from "next";
import { SITE_URL } from "@/lib/site";

/**
 * Only the marketing page is worth indexing. Everything else either redirects to sign-in for a
 * crawler (which would waste crawl budget on nothing) or is a signed-in surface.
 */
export default function robots(): MetadataRoute.Robots {
  return {
    rules: [{ userAgent: "*", allow: ["/welcome", "/login"], disallow: "/" }],
    sitemap: `${SITE_URL}/sitemap.xml`,
  };
}
