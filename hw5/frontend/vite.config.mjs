import { defineConfig } from "vite";
import react from "@vitejs/plugin-react";

export default defineConfig({
  plugins: [react()],
  // Dependency discovery is disabled for the managed Windows environment;
  // the installed React modules are still served and transformed by Vite.
  optimizeDeps: { disabled: true },
});
