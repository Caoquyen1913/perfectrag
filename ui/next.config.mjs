const API = process.env.PERFECTRAG_API_URL || "http://localhost:7777";

/** @type {import('next').NextConfig} */
export default {
  env: { PERFECTRAG_API_URL: API },
  async rewrites() {
    return [{ source: "/api/:path*", destination: `${API}/api/:path*` }];
  },
};
