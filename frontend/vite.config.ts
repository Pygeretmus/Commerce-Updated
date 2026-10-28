import { defineConfig } from "vite";
import react from "@vitejs/plugin-react";

// In development the API can be reached through the dev server (set VITE_API_URL=/api),
// which avoids CORS; /ws and /media are proxied too so live updates and photos work.
// (change the address if the backend runs elsewhere)
const backend = "http://127.0.0.1:8000";

export default defineConfig({
  plugins: [react()],
  server: {
    port: 5173,
    proxy: {
      "/api": backend,
      "/media": backend,
      "/ws": { target: backend, ws: true },
    },
  },
});
