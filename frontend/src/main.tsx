import React from "react";
import { createRoot } from "react-dom/client";
import "./styles.css";

const root = createRoot(document.getElementById("root")!);

console.log("[Sailor] main.tsx loaded, importing App...");

import("./App")
  .then((mod) => {
    console.log("[Sailor] App imported successfully");
    const App = mod.default;
    root.render(
      <React.StrictMode>
        <App />
      </React.StrictMode>
    );
  })
  .catch((err) => {
    console.error("[Sailor] Failed to load App:", err);
    root.render(
      <div style={{ padding: 20, color: "red", fontFamily: "Arial" }}>
        <h2>App 加载失败</h2>
        <pre>{err.message}{"\n"}{err.stack}</pre>
      </div>
    );
  });
