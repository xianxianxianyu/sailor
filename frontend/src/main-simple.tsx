import React from "react";
import { createRoot } from "react-dom/client";

console.log("=== main.tsx loaded ===");
console.log("React:", React);
console.log("createRoot:", createRoot);

function SimpleApp() {
  console.log("SimpleApp rendering");
  return (
    <div style={{ padding: "40px", fontFamily: "Arial, sans-serif" }}>
      <h1 style={{ color: "#0f766e" }}>✓ Sailor Frontend 正常运行</h1>
      <p>React 版本: {React.version}</p>
      <p>当前时间: {new Date().toLocaleString("zh-CN")}</p>
      <div style={{ marginTop: "20px", padding: "20px", background: "#f0f0f0", borderRadius: "8px" }}>
        <h2>系统状态</h2>
        <ul>
          <li>✓ HTML 加载成功</li>
          <li>✓ React 渲染成功</li>
          <li>✓ TypeScript 编译成功</li>
        </ul>
      </div>
      <button
        onClick={() => alert("按钮功能正常！")}
        style={{
          marginTop: "20px",
          padding: "10px 20px",
          background: "#0f766e",
          color: "white",
          border: "none",
          borderRadius: "4px",
          cursor: "pointer"
        }}
      >
        测试按钮
      </button>
    </div>
  );
}

const rootElement = document.getElementById("root");
console.log("Root element:", rootElement);

if (rootElement) {
  try {
    console.log("Creating React root...");
    const root = createRoot(rootElement);
    console.log("React root created:", root);

    console.log("Rendering app...");
    root.render(
      <React.StrictMode>
        <SimpleApp />
      </React.StrictMode>
    );
    console.log("App rendered successfully");
  } catch (error) {
    const err = error instanceof Error ? error : new Error(String(error));
    console.error("Render error:", err);
    rootElement.innerHTML = `
      <div style="padding: 20px; color: red;">
        <h1>渲染错误</h1>
        <pre>${err.message}\n${err.stack ?? ""}</pre>
      </div>
    `;
  }
} else {
  console.error("Root element not found!");
  document.body.innerHTML = '<h1 style="color: red; padding: 20px;">错误: 找不到 root 元素</h1>';
}
