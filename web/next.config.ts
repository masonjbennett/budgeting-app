import type { NextConfig } from "next";

/**
 * In production, `api/index.py` is a Vercel Function served at /api by the same
 * deployment, so the frontend calls a same-origin path and there is nothing to
 * configure. `next dev` has no Python runtime, so in development only, /api is
 * proxied to a local uvicorn:
 *
 *     web/.venv/Scripts/python.exe -m uvicorn index:app --app-dir api --port 8000
 *
 * The rewrite is gated on NODE_ENV so it cannot follow the app into production,
 * where it would point every request at a machine that does not exist.
 */
const DEV_API = process.env.DEV_API_URL ?? "http://127.0.0.1:8000";

const nextConfig: NextConfig = {
  async rewrites() {
    if (process.env.NODE_ENV !== "development") return [];
    return [{ source: "/api/:path*", destination: `${DEV_API}/api/:path*` }];
  },
};

export default nextConfig;
