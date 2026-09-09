/**
 * Public origin, used for canonical URLs, sitemap entries and absolute OG image URLs.
 * PUBLIC_BASE_URL is already set in production compose; the fallback keeps local builds sane.
 */
export const SITE_URL = process.env.PUBLIC_BASE_URL || "https://mocker.sapper.top";
