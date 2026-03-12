# 前端空白页面问题诊断与修复

**日期**: 2026-03-03
**问题**: 前端页面一片空白

---

## 🔍 问题诊断

### 1. 前端服务状态
- ✅ 前端进程正在运行（PID 42032）
- ✅ 监听端口 5173
- ⚠️ 只监听 IPv6 (::1)，不监听 IPv4 (0.0.0.0)

### 2. 网络配置问题
- ❌ 系统配置了代理 `http_proxy=127.0.0.1:7890`
- ❌ 访问本地前端时也走代理，导致 502 Bad Gateway
- ❌ Vite 默认只监听 IPv6

### 3. API 连接配置
- ⚠️ 没有 `.env` 文件配置 API 地址
- ⚠️ 没有配置代理转发

---

## ✅ 已完成的修复

### 1. 修复 Vite 配置

**文件**: `frontend/vite.config.ts`

**修改内容**:
```typescript
export default defineConfig({
  plugins: [react()],
  server: {
    port: 5173,
    host: "0.0.0.0", // 监听所有接口，包括 IPv4
    proxy: {
      "/api": {
        target: "http://localhost:8000",
        changeOrigin: true,
        rewrite: (path) => path.replace(/^\/api/, ""),
      },
    },
  },
});
```

**效果**:
- ✅ 前端现在监听 0.0.0.0:5173（所有接口）
- ✅ 添加了 API 代理，可以通过 `/api/*` 访问后端
- ✅ 避免 CORS 问题

### 2. 创建环境配置文件

**文件**: `frontend/.env`

**内容**:
```
VITE_API_BASE=http://localhost:8000
```

**效果**:
- ✅ 明确配置后端 API 地址
- ✅ 前端可以正确连接到后端

---

## 🔧 需要的操作

### 重启前端服务

由于修改了 `vite.config.ts`，需要重启前端：

```bash
# 1. 停止当前前端进程（Ctrl+C）

# 2. 重新启动前端
cd sailor/frontend
npm run dev
```

### 验证修复

1. **检查前端是否可访问**:
   ```bash
   curl http://localhost:5173
   ```
   应该返回 HTML 内容

2. **在浏览器中访问**:
   ```
   http://localhost:5173
   ```
   应该看到 Sailor 界面

3. **检查 API 连接**:
   打开浏览器开发者工具（F12），查看：
   - Console 标签：是否有 JavaScript 错误
   - Network 标签：API 请求是否成功

---

## 🌐 网络配置建议

### 方案 1: 配置代理例外（推荐）

在系统环境变量中添加：
```bash
NO_PROXY=localhost,127.0.0.1,::1
```

或在浏览器代理设置中添加例外：
- localhost
- 127.0.0.1
- ::1

### 方案 2: 临时禁用代理

访问本地开发服务时，临时禁用代理：
```bash
# Windows PowerShell
$env:http_proxy=""
$env:https_proxy=""

# 或在浏览器中切换到"直接连接"模式
```

---

## 📊 前后端连接验证

### 后端健康检查
```bash
curl http://localhost:8000/healthz
# 应该返回: {"status":"ok"}
```

### 前端访问后端
前端现在可以通过两种方式访问后端：

1. **直接访问**（使用 VITE_API_BASE）:
   ```javascript
   fetch('http://localhost:8000/tags')
   ```

2. **通过代理**（推荐，避免 CORS）:
   ```javascript
   fetch('/api/tags')
   ```

---

## 🐛 常见问题排查

### 问题 1: 前端仍然空白

**检查**:
1. 浏览器控制台是否有错误
2. Network 标签是否有失败的请求
3. 前端是否正确加载了 JavaScript 文件

**解决**:
```bash
# 清理前端缓存并重新构建
cd sailor/frontend
rm -rf node_modules/.vite
npm run dev
```

### 问题 2: API 请求失败

**检查**:
1. 后端是否在运行（http://localhost:8000/healthz）
2. 浏览器控制台是否有 CORS 错误
3. Network 标签中请求的 URL 是否正确

**解决**:
- 使用代理方式访问 API（`/api/*`）
- 或在后端添加 CORS 配置

### 问题 3: 502 Bad Gateway

**原因**: 代理配置问题

**解决**:
1. 在浏览器代理设置中添加 localhost 到例外列表
2. 或临时禁用代理访问本地服务

---

## 📝 前端架构说明

### 目录结构
```
frontend/
├── src/
│   ├── App.tsx           # 主应用组件
│   ├── main.tsx          # 入口文件
│   ├── api.ts            # API 客户端
│   ├── types.ts          # TypeScript 类型定义
│   ├── styles.css        # 全局样式
│   ├── components/       # 可复用组件
│   ├── pages/            # 页面组件
│   └── hooks/            # 自定义 Hooks
├── index.html            # HTML 模板
├── vite.config.ts        # Vite 配置
├── .env                  # 环境变量（新增）
└── package.json          # 依赖配置
```

### 技术栈
- **框架**: React 19
- **构建工具**: Vite 7
- **语言**: TypeScript 5
- **可视化**: react-force-graph

### API 集成
- 所有 API 调用在 `src/api.ts` 中定义
- 使用 `fetch` API 进行 HTTP 请求
- 支持环境变量配置 API 地址

---

## ✅ 修复清单

- [x] 修改 `vite.config.ts` 监听所有接口
- [x] 添加 API 代理配置
- [x] 创建 `.env` 文件配置 API 地址
- [x] 编写诊断文档
- [ ] 重启前端服务（需要用户操作）
- [ ] 在浏览器中验证（需要用户操作）

---

## 🎯 预期结果

重启前端后，应该能够：
1. ✅ 在浏览器中看到 Sailor 界面
2. ✅ 导航栏显示所有功能模块
3. ✅ API 请求成功连接到后端
4. ✅ 可以查看 Sniffer、KB、Tags 等功能

---

**修复完成时间**: 2026-03-03
**状态**: 配置已完成，等待重启前端验证
