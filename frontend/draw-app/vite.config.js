import { defineConfig } from "vite";
import react from "@vitejs/plugin-react";

export default defineConfig({
  plugins: [react()],
  base: "/draw/",
  build: {
    outDir: "../draw",
    emptyOutDir: false,
  },
});
