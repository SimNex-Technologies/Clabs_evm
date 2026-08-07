/** @type {import('next').NextConfig} */
const nextConfig = {
  // Produces .next/standalone: a minimal server.js + only the node_modules
  // it actually needs, so the school PC needs nothing but a portable Node.js
  // runtime - no `npm install` on-site.
  output: "standalone",

  // The kiosk launcher opens http://127.0.0.1:3000 (not "localhost"), and in
  // dev mode Next.js treats that as a distinct, untrusted origin and blocks
  // HMR/static-chunk requests from it. Production (`next start`/standalone)
  // doesn't have this check at all - this only matters for `npm run dev`.
  allowedDevOrigins: ["127.0.0.1"],

  // The browser only ever talks to this Next.js server. These two path
  // prefixes are silently forwarded to the FastAPI backend server-side, so
  // there's no CORS to configure and the page code below (api.js) can use
  // the exact same relative paths as when FastAPI served everything itself.
  async rewrites() {
    const backend = process.env.BACKEND_ORIGIN || "http://127.0.0.1:8000";
    return [
      { source: "/api/:path*", destination: `${backend}/api/:path*` },
      { source: "/symbols/:path*", destination: `${backend}/symbols/:path*` },
    ];
  },
};

export default nextConfig;
