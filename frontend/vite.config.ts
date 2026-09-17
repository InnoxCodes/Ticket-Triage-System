import { fileURLToPath, URL } from "node:url";

import tailwindcss from "@tailwindcss/vite";
import react from "@vitejs/plugin-react";
import { defineConfig } from "vite";

// In development the API is reached through this proxy, so the browser only
// ever talks to its own origin. That removes CORS from local dev entirely and
// means the frontend code uses the same relative URLs in dev as it does when a
// reverse proxy fronts both in production. A cross-origin deployment (Vercel +
// Railway) instead sets VITE_API_URL at build time.
const API_TARGET = process.env.VITE_DEV_API_TARGET ?? "http://127.0.0.1:8000";

export default defineConfig({
  plugins: [react(), tailwindcss()],
  resolve: {
    alias: {
      "@": fileURLToPath(new URL("./src", import.meta.url)),
    },
  },
  server: {
    port: 5173,
    strictPort: true,
    proxy: {
      "/api": { target: API_TARGET, changeOrigin: true },
      "/ws": { target: API_TARGET.replace(/^http/, "ws"), ws: true },
    },
  },
  preview: {
    port: 4173,
  },
});
