#!/usr/bin/env node
/**
 * FairDataHive dev server guard — one Vite instance on 5173 only.
 * Port 5174 is an orphan from an older second Vite when 5173 was busy; we always stop it.
 */
import { execSync, spawn } from "node:child_process";
import { fileURLToPath } from "node:url";
import path from "node:path";

const FRONTEND_DIR = path.resolve(path.dirname(fileURLToPath(import.meta.url)), "..");
const DEV_PORT = 5173;
const ORPHAN_PORT = 5174;

function sleep(ms) {
  return new Promise((r) => setTimeout(r, ms));
}

function pidsOnPort(port) {
  try {
    const out = execSync(`lsof -t -iTCP:${port} -sTCP:LISTEN 2>/dev/null`, {
      encoding: "utf8",
    }).trim();
    return out ? out.split("\n").map((s) => s.trim()).filter(Boolean) : [];
  } catch {
    return [];
  }
}

function cmdline(pid) {
  try {
    return execSync(`ps -p ${pid} -o args= 2>/dev/null`, { encoding: "utf8" }).trim();
  } catch {
    return "";
  }
}

function isViteOrNodeDev(pid) {
  const cmd = cmdline(pid);
  if (!cmd) return false;
  if (cmd.includes("vite")) return true;
  if (cmd.includes("node") && cmd.includes("fairdatahive")) return true;
  if (cmd.includes("node") && cmd.includes(FRONTEND_DIR)) return true;
  return false;
}

function stopPort(port, { viteOnly = true } = {}) {
  const pids = pidsOnPort(port);
  let stopped = 0;
  for (const pid of pids) {
    if (!viteOnly || isViteOrNodeDev(pid)) {
      try {
        process.kill(Number(pid), "SIGTERM");
        stopped += 1;
      } catch {
        /* already gone */
      }
    }
  }
  return stopped;
}

async function stopAll() {
  const n4 = stopPort(ORPHAN_PORT, { viteOnly: false });
  const n3 = stopPort(DEV_PORT, { viteOnly: false });
  if (n3 + n4 > 0) {
    await sleep(400);
  }
  console.log(
    n3 + n4 > 0
      ? `Stopped dev server(s) on port ${DEV_PORT} and/or ${ORPHAN_PORT}.`
      : `No FairDataHive dev server on ${DEV_PORT} or ${ORPHAN_PORT}.`,
  );
}

async function ensureAndStart() {
  // Legacy: second Vite bound 5174 when 5173 was taken — always clear it.
  const orphan = stopPort(ORPHAN_PORT, { viteOnly: false });
  if (orphan > 0) {
    await sleep(300);
    console.log(`Stopped orphan dev server on port ${ORPHAN_PORT}.`);
  }

  const onDev = pidsOnPort(DEV_PORT);
  const viteOnDev = onDev.filter(isViteOrNodeDev);
  const foreign = onDev.filter((pid) => !isViteOrNodeDev(pid));

  if (foreign.length > 0) {
    console.error(
      `Port ${DEV_PORT} is in use by a non-Vite process (PID ${foreign.join(", ")}).`,
    );
    console.error(`Free the port, then run: npm run dev`);
    process.exit(1);
  }

  if (viteOnDev.length > 0) {
    console.log(`Restarting Vite on http://127.0.0.1:${DEV_PORT} ...`);
    stopPort(DEV_PORT);
    await sleep(400);
  }

  const child = spawn("npx", ["vite"], {
    cwd: FRONTEND_DIR,
    stdio: "inherit",
    shell: false,
    env: { ...process.env, FORCE_COLOR: "1" },
  });
  child.on("exit", (code) => process.exit(code ?? 0));
}

const mode = process.argv.includes("--stop") ? "stop" : "start";
if (mode === "stop") {
  await stopAll();
} else {
  await ensureAndStart();
}
