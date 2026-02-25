const { app, BrowserWindow, dialog } = require("electron");
const http = require("http");
const path = require("path");
const { spawn } = require("child_process");

const PROJECT_ROOT = path.join(__dirname, "..");
const FRONTEND_URL = "http://localhost:5173";
const BACKEND_HEALTH_URL = "http://127.0.0.1:8000/healthz";

const CHILDREN = [];
let isShuttingDown = false;

function createChildEnv() {
  const env = { ...process.env };
  if (process.platform === "win32") {
    env.PYTHONUTF8 = env.PYTHONUTF8 || "1";
    env.PYTHONIOENCODING = env.PYTHONIOENCODING || "utf-8";
  }
  return env;
}

function spawnScript(scriptName) {
  const isWindows = process.platform === "win32";
  const command = isWindows ? "cmd.exe" : "npm";
  const args = isWindows ? ["/d", "/s", "/c", `npm.cmd run ${scriptName}`] : ["run", scriptName];
  const child = spawn(command, args, {
    cwd: PROJECT_ROOT,
    stdio: isWindows ? "ignore" : "pipe",
    shell: false,
    env: createChildEnv(),
    windowsHide: true,
  });

  if (!isWindows) {
    if (child.stdout) {
      child.stdout.on("data", (chunk) => process.stdout.write(chunk));
    }
    if (child.stderr) {
      child.stderr.on("data", (chunk) => process.stderr.write(chunk));
    }
  }

  CHILDREN.push(child);
  child.on("exit", async (code) => {
    if (isShuttingDown) return;
    if (typeof code === "number" && code !== 0) {
      if (scriptName === "dev:backend" && (await pingHealth(BACKEND_HEALTH_URL))) {
        // If backend is already serving on the target port, do not treat bind failure as fatal.
        return;
      }
      if (scriptName === "dev:frontend" && (await ping(FRONTEND_URL))) {
        return;
      }
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
    if (await checker(url)) {
      return;
    }
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

function cleanupChildren() {
  for (const child of CHILDREN) {
    if (!child || !child.pid) continue;

    if (process.platform === "win32") {
      spawn(`taskkill /pid ${child.pid} /T /F`, {
        shell: true,
        stdio: "ignore",
      });
    } else {
      child.kill("SIGTERM");
    }
  }
}

async function bootstrap() {
  const backendAlreadyRunning = await pingHealth(BACKEND_HEALTH_URL);
  if (!backendAlreadyRunning) {
    spawnScript("dev:backend");
  }

  const frontendAlreadyRunning = await ping(FRONTEND_URL);
  if (!frontendAlreadyRunning) {
    spawnScript("dev:frontend");
  }

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
  cleanupChildren();
  app.quit();
});

app.on("before-quit", () => {
  isShuttingDown = true;
  cleanupChildren();
});
