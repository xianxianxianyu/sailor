import { defineConfig } from "vite";
import react from "@vitejs/plugin-react";
export default defineConfig({
    plugins: [react()],
    server: {
        port: 5174,
        host: "0.0.0.0",
        strictPort: false,
        cors: true,
        proxy: {
            "/api": {
                target: "http://localhost:8000",
                changeOrigin: true,
                rewrite: function (path) { return path.replace(/^\/api/, ""); },
            },
        },
    },
    optimizeDeps: {
        include: ['react', 'react-dom'],
    },
});
