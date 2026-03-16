import type { NextConfig } from "next";
import path from "path";

const nextConfig: NextConfig = {
  output: "standalone",
  turbopack: {
    root: path.resolve(__dirname),
  },
  webpack: (config) => {
    // Ensure module resolution (e.g. tailwindcss) uses frontend as context,
    // so node_modules is resolved from frontend/ even when run from repo root.
    config.context = path.resolve(__dirname);
    return config;
  },
};

export default nextConfig;
