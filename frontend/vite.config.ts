import fs from "node:fs";
import path from "node:path";
import { fileURLToPath } from "node:url";
import react from "@vitejs/plugin-react";
import { defineConfig, type Plugin } from "vite";

const __dirname = path.dirname(fileURLToPath(import.meta.url));
const docsRoot = path.resolve(__dirname, "../docs");

function contentType(filePath: string): string {
  if (filePath.endsWith(".html")) return "text/html; charset=utf-8";
  if (filePath.endsWith(".css")) return "text/css; charset=utf-8";
  if (filePath.endsWith(".js")) return "application/javascript; charset=utf-8";
  if (filePath.endsWith(".svg")) return "image/svg+xml";
  if (filePath.endsWith(".png")) return "image/png";
  if (filePath.endsWith(".ico")) return "image/x-icon";
  return "application/octet-stream";
}

/** Serve fairdatahive/docs at /docs during Vite dev and preview. */
function serveProjectDocs(): Plugin {
  const middleware = (
    req: { url?: string },
    res: {
      statusCode: number;
      setHeader: (k: string, v: string) => void;
      end: (s?: string) => void;
    },
    next: () => void
  ) => {
    const raw = req.url ?? "";
    if (!raw.startsWith("/docs")) return next();

    if (raw === "/docs" || raw.startsWith("/docs?")) {
      const q = raw.includes("?") ? raw.slice(raw.indexOf("?")) : "";
      res.statusCode = 301;
      res.setHeader("Location", `/docs/${q}`);
      res.end();
      return;
    }

    let rel = decodeURIComponent(raw.slice("/docs".length) || "/");
    const q = rel.indexOf("?");
    if (q >= 0) rel = rel.slice(0, q);
    if (rel === "" || rel === "/") rel = "/index.html";

    const filePath = path.normalize(path.join(docsRoot, rel));
    if (!filePath.startsWith(docsRoot)) {
      res.statusCode = 403;
      res.end("Forbidden");
      return;
    }
    if (!fs.existsSync(filePath) || fs.statSync(filePath).isDirectory()) {
      next();
      return;
    }

    res.statusCode = 200;
    res.setHeader("Content-Type", contentType(filePath));
    res.end(fs.readFileSync(filePath));
  };

  return {
    name: "serve-project-docs",
    configureServer(server) {
      server.middlewares.use(middleware);
    },
    configurePreviewServer(server) {
      server.middlewares.use(middleware);
    },
  };
}

const apiProxy = process.env.VITE_API_PROXY || "http://localhost:8002";

export default defineConfig({
  plugins: [serveProjectDocs(), react()],
  server: {
    port: 5173,
    strictPort: true,
    host: "127.0.0.1",
    proxy: {
      "/api": {
        target: apiProxy,
        changeOrigin: true,
      },
      "/swagger": {
        target: apiProxy,
        changeOrigin: true,
      },
      "/openapi.json": {
        target: apiProxy,
        changeOrigin: true,
      },
      "/redoc": {
        target: apiProxy,
        changeOrigin: true,
      },
    },
  },
  preview: {
    port: 4173,
    strictPort: true,
    host: "127.0.0.1",
  },
  build: {
    outDir: "dist",
    emptyOutDir: true,
    rollupOptions: {
      output: {
        manualChunks: {
          vendor: ["react", "react-dom", "react-router-dom"],
        },
      },
    },
  },
});
