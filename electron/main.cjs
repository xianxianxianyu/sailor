const { app, BrowserWindow, dialog } = require("electron");
const http = require("http");
const path = require("path");
const { spawn } = require("child_process");

const PROJECT_ROOT = path.join(__dirname, "..");
const FRONTEND_URL = "http://localhost:5173";
const BACKEND_HEALTH_URL = "http://127.0.0.1:8000/healthz";
const BACKEND_PORT = 8000;
const FRONTEND_PORT = 5173;

const CHILDREN = [];
let isShuttingDown = false;
let cleanedUp = false;

function createChildEnv() {
  const env = { ...process.env };
  if (process.platform === "win32") {
    env.PYTHONUTF8 = env.PYTHONUTF8 || "1";
    env.PYTHONIOENCODING = env.PYTHONIOENCODING || "utf-8";
  }
  return env;
}

// Kill any process listening on the given port (cross-platform)
async function killByPort(port) {
  if (process.platform !== "win32") {
    await new Promise((resolve) => {
      spawn("sh", ["-c", `lsof -ti:${port} | xargs kill -9 2>/dev/null; true`], {
        stdio: "ignore",
      }).on("close", resolve);
    });
    return;
  }

  // Windows: parse netstat output to find LISTENING PIDs
  const netstat = spawn("netstat", ["-ano"], {
    windowsHide: true,
    stdio: ["ignore", "pipe", "ignore"],
  });

  let output = "";
  netstat.stdout.on("data", (d) => (output += d));

  await new Promise((resolve) => netstat.on("close", resolve));

  const pids = new Set();
  for (const line of output.split("\n")) {
    if (line.includes(`:${port} `) || line.includes(`:${port}\t`)) {
      if (line.toUpperCase().includes("LISTENING")) {
        const parts = line.trim().split(/\s+/);
        const pid = parts[parts.length - 1];
        if (pid && /^\d+$/.test(pid) && pid !== "0") {
          pids.add(pid);
        }
      }
    }
  }

  for (const pid of pids) {
    await new Promise((resolve) => {
      spawn("taskkill", ["/F", "/PID", pid, "/T"], {
        stdio: "ignore",
        windowsHide: true,
      }).on("close", resolve);
    });
  }
}

function spawnScript(scriptName) {
  const isWindows = process.platform === "win32";
  const command = isWindows ? "cmd.exe" : "npm";
  const args = isWindows ? ["/d", "/s", "/c", `npm.cmd run ${scriptName}`] : ["run", scriptName];
  const child = spawn(command, args, {
    cwd: PROJECT_ROOT,
    stdio: "pipe",
    shell: false,
    env: createChildEnv(),
    windowsHide: true,
  });

  if (child.stdout) {
    child.stdout.on("data", (chunk) => process.stdout.write(chunk));
  }
  if (child.stderr) {
    child.stderr.on("data", (chunk) => process.stderr.write(chunk));
  }

  CHILDREN.push(child);
  child.on("exit", (code) => {
    if (isShuttingDown) return;
    if (typeof code === "number" && code !== 0) {
      dialog.showErrorBox("Sailor", `Script '${scriptName}' exited with code ${code}.`);
      app.quit();
    }
  });

  return child;
}

function ping(url) {
  return new Promise((resolve) => {
    const req = http.get(url, (res) => {
      resolve(res.statusCode >= 200 && res.statusCode < 500);
    });
    req.on("error", () => resolve(false));
    req.setTimeout(1500, () => {
      req.destroy();
      resolve(false);
    });
  });
}

function pingHealth(url) {
  return new Promise((resolve) => {
    const req = http.get(url, (res) => {
      resolve(res.statusCode === 200);
    });
    req.on("error", () => resolve(false));
    req.setTimeout(1500, () => {
      req.destroy();
      resolve(false);
    });
  });
}

async function waitForUrl(url, timeoutMs, checker = ping) {
  const started = Date.now();
  while (Date.now() - started < timeoutMs) {
    if (await checker(url)) return;
    await new Promise((resolve) => setTimeout(resolve, 700));
  }
  throw new Error(`Timed out waiting for ${url}`);
}

function createWindow() {
  const mainWindow = new BrowserWindow({
    width: 1400,
    height: 900,
    minWidth: 1100,
    minHeight: 720,
    show: false,
    webPreferences: {
      preload: path.join(__dirname, "preload.cjs"),
      contextIsolation: true,
      nodeIntegration: false,
    },
  });

  mainWindow.once("ready-to-show", () => {
    mainWindow.show();
  });

  setTimeout(() => {
    if (!mainWindow.isVisible()) {
      mainWindow.show();
    }
  }, 8000);

  mainWindow.loadURL(FRONTEND_URL);
}

async function cleanupChildren() {
  if (cleanedUp) return;
  cleanedUp = true;

  // Kill tracked child processes
  for (const child of CHILDREN) {
    if (!child || !child.pid) continue;
    if (process.platform === "win32") {
      spawn("taskkill", ["/F", "/PID", String(child.pid), "/T"], {
        shell: false,
        stdio: "ignore",
        windowsHide: true,
      });
    } else {
      child.kill("SIGTERM");
    }
  }

  // Port-based fallback: ensure ports are freed even for pre-existing processes
  await Promise.all([killByPort(BACKEND_PORT), killByPort(FRONTEND_PORT)]);
}

async function bootstrap() {
  // Always restart: kill any leftover processes from previous sessions
  console.log("[Sailor] Stopping any existing backend/frontend processes...");
  await Promise.all([killByPort(BACKEND_PORT), killByPort(FRONTEND_PORT)]);

  // Brief pause to let OS release ports
  await new Promise((resolve) => setTimeout(resolve, 500));

  console.log("[Sailor] Starting backend and frontend...");
  spawnScript("dev:backend");
  spawnScript("dev:frontend");

  await waitForUrl(BACKEND_HEALTH_URL, 120_000, pingHealth);
  await waitForUrl(FRONTEND_URL, 120_000);
  createWindow();
}

app.whenReady().then(() => {
  return bootstrap().catch((error) => {
    dialog.showErrorBox("Sailor", error.stack || String(error));
    app.quit();
  });
});

app.on("window-all-closed", () => {
  isShuttingDown = true;
  cleanupChildren().finally(() => app.quit());
});

app.on("before-quit", () => {
  isShuttingDown = true;
  cleanupChildren();
});
