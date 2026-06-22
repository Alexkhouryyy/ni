import { defineConfig } from "vite";

export default defineConfig({
  server: {
    port: 5174,
    host: true, // Expose to local network so phone can connect
  },
  build: {
    outDir: "dist",
  },
});
