import { app, BrowserWindow, dialog } from 'electron';
import { spawn } from 'child_process';
import { createConnection } from 'net';
import { readFileSync } from 'fs';
import { homedir } from 'os';
import path from 'path';

const GATEWAY_PORT = 18789;
const BASE_URL     = `http://127.0.0.1:${GATEWAY_PORT}`;
const POLL_MS      = 500;
const TIMEOUT_MS   = 30_000;

let gatewayProcess  = null;
let mainWindow      = null;
let intentionalQuit = false;

// ── 1. 检测端口是否已有进程监听 ────────────────────────────────────────────────
function isPortOpen(port) {
  return new Promise((resolve) => {
    const conn = createConnection({ host: '127.0.0.1', port });
    conn.setTimeout(600);
    conn.once('connect',  () => { conn.destroy(); resolve(true);  });
    conn.once('error',    () => { conn.destroy(); resolve(false); });
    conn.once('timeout',  () => { conn.destroy(); resolve(false); });
  });
}

// ── 2. 从配置文件读取 gateway token ───────────────────────────────────────────
function readGatewayToken() {
  try {
    const cfgPath = path.join(homedir(), '.openclaw', 'openclaw.json');
    const cfg = JSON.parse(readFileSync(cfgPath, 'utf8'));
    return cfg?.gateway?.auth?.token ?? null;
  } catch {
    return null;
  }
}

// ── 3. 启动我们自己的 gateway（仅当端口未被占用时）────────────────────────────
function startGateway() {
  console.log('[desktop] No gateway detected, launching own gateway...');

  const env = {
    ...process.env,
    PATH: `/opt/homebrew/bin:/usr/local/bin:/usr/bin:/bin:${process.env.PATH ?? ''}`,
  };

  gatewayProcess = spawn(
    'openclaw',
    ['gateway', 'run', '--allow-unconfigured', '--auth', 'none'],
    { detached: false, stdio: ['ignore', 'pipe', 'pipe'], env }
  );

  // 持续消费管道，防止子进程因缓冲区满而阻塞
  gatewayProcess.stdout.on('data', (d) => process.stdout.write(`[gateway] ${d}`));
  gatewayProcess.stderr.on('data', (d) => process.stderr.write(`[gateway] ${d}`));

  gatewayProcess.on('error', (err) => {
    if (intentionalQuit) return;
    dialog.showErrorBox('OpenClaw 启动失败',
      `无法启动 openclaw gateway：\n${err.message}\n\n请确认已全局安装 openclaw CLI。`);
    safeQuit();
  });

  gatewayProcess.on('exit', (code, signal) => {
    console.log(`[desktop] Gateway exited (code=${code} signal=${signal})`);
    if (intentionalQuit) return;

    const detail = code != null ? `进程退出码：${code}` : `被信号终止：${signal}`;
    dialog.showMessageBox({
      type: 'error',
      title: 'OpenClaw Gateway 已停止',
      message: 'Gateway 进程意外退出，应用将关闭。',
      detail,
      buttons: ['确定'],
    }).then(() => safeQuit());
  });
}

// ── 4. 轮询等待端口就绪 ────────────────────────────────────────────────────────
function waitForGateway() {
  return new Promise((resolve, reject) => {
    const deadline = Date.now() + TIMEOUT_MS;

    function probe() {
      isPortOpen(GATEWAY_PORT).then((open) => {
        if (open) { resolve(); return; }
        if (Date.now() >= deadline) {
          reject(new Error(`OpenClaw gateway 未在 ${TIMEOUT_MS / 1000}s 内就绪。`));
        } else {
          setTimeout(probe, POLL_MS);
        }
      });
    }

    probe();
  });
}

// ── 5. 创建主窗口 ──────────────────────────────────────────────────────────────
function createWindow(token) {
  const url = token ? `${BASE_URL}/#token=${token}` : BASE_URL;
  console.log('[desktop] Loading', token ? `${BASE_URL}/#token=<hidden>` : BASE_URL);

  mainWindow = new BrowserWindow({
    width: 1280, height: 860,
    minWidth: 800, minHeight: 600,
    title: 'OpenClaw',
    webPreferences: { nodeIntegration: false, contextIsolation: true },
  });

  mainWindow.loadURL(url);
  mainWindow.on('closed', () => { mainWindow = null; });
}

// ── 6. 应用启动 ────────────────────────────────────────────────────────────────
app.whenReady().then(async () => {
  const alreadyRunning = await isPortOpen(GATEWAY_PORT);

  if (alreadyRunning) {
    // 复用已有的系统 gateway，读取 token 做认证
    console.log('[desktop] Existing gateway detected on port', GATEWAY_PORT);
    const token = readGatewayToken();
    createWindow(token);
  } else {
    // 自己启动 gateway（--auth none，不需要 token）
    startGateway();
    try {
      await waitForGateway();
      console.log('[desktop] Gateway ready — opening window.');
      createWindow(null);
    } catch (err) {
      dialog.showErrorBox('OpenClaw 启动超时', err.message);
      safeQuit();
    }
  }
});

app.on('window-all-closed', () => safeQuit());

// ── 7. 安全退出 ────────────────────────────────────────────────────────────────
function safeQuit() {
  if (intentionalQuit) return;
  intentionalQuit = true;
  killGateway();
  app.quit();
}

function killGateway() {
  if (gatewayProcess && !gatewayProcess.killed) {
    console.log('[desktop] Sending SIGTERM to gateway...');
    try { gatewayProcess.kill('SIGTERM'); } catch (_) {}
    gatewayProcess = null;
  }
}
