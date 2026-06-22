import { defineConfig } from "vite";
import { VitePWA } from "vite-plugin-pwa";

export default defineConfig({
  plugins: [
    VitePWA({
      registerType: "autoUpdate",
      // We supply our own manifest.json via public/
      manifest: false,
      workbox: {
        // Cache all static assets
        globPatterns: ["**/*.{js,css,html,png,svg,ico}"],
        // Don't cache API or WS endpoints
        navigateFallbackDenylist: [/^\/api\//, /^\/ws\//],
        runtimeCaching: [],
      },
    }),
  ],
  server: {
    port: 5173,
    // Allow access from Tailscale, LAN, etc. Any *.ts.net host (Tailscale MagicDNS)
    // and any private/local IPs are accepted.
    allowedHosts: [
      "localhost",
      ".ts.net",     // matches anything ending in .ts.net (Tailscale)
      ".local",      // mDNS local hostnames
    ],
    proxy: {
      "/ws": {
        target: "https://127.0.0.1:8340",
        ws: true,
        secure: false,
        changeOrigin: true,
      },
      "/api": {
        target: "https://127.0.0.1:8340",
        secure: false,
        changeOrigin: true,
      },
    },
  },
  build: {
    outDir: "dist",
  },
});
