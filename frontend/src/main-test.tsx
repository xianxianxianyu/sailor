import React from "react";
import { createRoot } from "react-dom/client";

// 最小化测试 - 不导入任何其他组件
function TestApp() {
  return (
    <div style={{ padding: "20px", fontFamily: "Arial" }}>
      <h1 style={{ color: "green" }}>✓ React 正常工作！</h1>
      <p>如果你能看到这个页面，说明 React 渲染正常。</p>
      <p>当前时间: {new Date().toLocaleString()}</p>
      <button onClick={() => alert("按钮点击正常！")}>
        测试按钮
      </button>
    </div>
  );
}

const root = document.getElementById("root");
if (root) {
  createRoot(root).render(
    <React.StrictMode>
      <TestApp />
    </React.StrictMode>
  );
} else {
  document.body.innerHTML = '<h1 style="color: red;">错误: 找不到 root 元素</h1>';
}
