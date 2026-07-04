import type { NextConfig } from "next";

const supabaseUrl = process.env.NEXT_PUBLIC_SUPABASE_URL;

const nextConfig: NextConfig = {
  async rewrites() {
    if (!supabaseUrl) return [];
    return [
      {
        // Proxies Supabase Storage public assets through our own domain, so
        // third parties (e.g. TikTok's Content Posting API, which requires
        // proof of ownership of any URL it's asked to pull media from) see
        // vancearchives.com instead of the raw *.supabase.co host.
        source: "/media/:path*",
        destination: `${supabaseUrl}/storage/v1/object/public/:path*`,
      },
    ];
  },
};

export default nextConfig;
