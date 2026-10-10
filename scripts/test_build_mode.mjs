#!/usr/bin/env node
/**
 * 构建并发模式（build_mode）测试。
 *
 * 运行方式：
 *   node scripts/test_build_mode.mjs
 *
 * 行为：
 *   1. go build 编译 server/quartz-service.exe；
 *   2. 用独立端口（默认 9799）与独立 output/cache 目录起临时实例；
 *   3. 用 uv run python 生成 3 个业务域的内容（input/{domain}），再通过 API 建域；
 *   4. 【串行模式】同时触发 3 个 build：断言 1 个 Accepted + 2 个 Queued，
 *      且全程 running 数恒 <= 1，最终 3 个都构建成功；
 *   5. 【并行模式】同时触发 3 个 build：断言 3 个 Accepted，running 数曾 >= 2，
 *      最终 3 个都构建成功。
 *
 * 环境变量：
 *   TEST_PORT   服务端口（默认 9799）
 *   KEEP_TMP=1  结束后保留 tmp-build-mode-test/（默认保留，便于查看产物）
 */

import { spawn, spawnSync } from 'child_process';
import fs from 'fs/promises';
import path from 'path';
import { fileURLToPath } from 'url';

const __dirname = path.dirname(fileURLToPath(import.meta.url));
const ROOT = path.resolve(__dirname, '..');
const TMP = path.join(ROOT, 'tmp-build-mode-test');
const SERVER_PORT = Number(process.env.TEST_PORT || 9799);
const BASE_URL = `http://127.0.0.1:${SERVER_PORT}`;
const AUTH = { user: 'admin', pwd: 'password123' };

const DOMAINS = ['mode-a', 'mode-b', 'mode-c'];

const results = [];
function ok(name, note) {
  results.push({ name, status: 'PASS', note: note || '' });
  console.log(`  [PASS] ${name}${note ? ' — ' + note : ''}`);
}
function bad(name, note) {
  results.push({ name, status: 'FAIL', note: note || '' });
  console.log(`  [FAIL] ${name}${note ? ' — ' + note : ''}`);
}
function assertTrue(cond, msg) {
  if (!cond) throw new Error(msg);
}
function abs(p) {
  return path.resolve(ROOT, p).replace(/\\/g, '/');
}
function sleep(ms) {
  return new Promise((r) => setTimeout(r, ms));
}

// ============ HTTP ============
function qs(params) {
  const u = new URLSearchParams();
  for (const [k, v] of Object.entries(params)) if (v != null) u.set(k, String(v));
  return u.toString();
}
async function http(method, urlPath, body) {
  const sep = urlPath.includes('?') ? '&' : '?';
  const url = `${BASE_URL}${urlPath}${sep}${qs(AUTH)}`;
  const init = { method, headers: {} };
  if (body !== undefined) {
    init.headers['Content-Type'] = 'application/json';
    init.body = JSON.stringify(body);
  }
  const res = await fetch(url, init);
  const text = await res.text();
  let json = null;
  try {
    json = JSON.parse(text);
  } catch {
    /* non-json ok */
  }
  return { status: res.status, text, json };
}

// ============ 服务生命周期 ============
async function buildServer() {
  const serverDir = path.join(ROOT, 'server');
  // 用独立 exe 名，避免与已在运行、占用 quartz-service.exe 的实例冲突
  const exeName = 'quartz-service-test.exe';
  const proc = spawn('go', ['build', '-o', exeName, '.'], {
    cwd: serverDir,
    stdio: 'pipe',
    shell: true,
  });
  return new Promise((resolve, reject) => {
    let out = '';
    proc.stdout.on('data', (d) => (out += d));
    proc.stderr.on('data', (d) => (out += d));
    proc.on('close', (code) =>
      code !== 0 ? reject(new Error(`go build failed: ${out}`)) : resolve(path.join(serverDir, exeName)),
    );
  });
}

async function writeTempConfig(mode) {
  const cfg = {
    version: '1.0.1-buildmode-test',
    listen_addr: `0.0.0.0:${SERVER_PORT}`,
    base_url: 'localhost',
    build_mode: mode, // 被测开关
    optional_param: 'reset',
    forbidden_page: abs('server/401.html'),
    attachments: { directory: abs('input/assets'), url_path: 'assets' },
    auth: {
      user_param: 'user',
      pwd_param: 'pwd',
      user: AUTH.user,
      pwd: AUTH.pwd,
      cookie_max_age: 0,
    },
    command: {
      work_dir: abs('quartz5'),
      interpreter: 'node',
      interpreter_args: '--no-deprecation',
      script: './quartz/bootstrap-cli.mjs',
      args: 'build --sqlite --concurrency=2',
      optional_flag: '--reset',
    },
    input_dir: abs('input'),
    output_dir: path.join(TMP, `output-${mode}`).replace(/\\/g, '/'),
    settings_dir: abs('settings'),
    template_file: abs('quartz5/quartz.config.yaml'),
    cache_dir: path.join(TMP, `cache-${mode}`).replace(/\\/g, '/'),
    compression: {
      enabled: true,
      level: 6,
      min_size_kb: 1,
      types: ['text/html', 'text/css', 'text/javascript', 'application/javascript', 'application/json', 'text/xml', 'application/xml'],
    },
    chunked_transfer: { enabled: true, threshold_kb: 1024, buffer_size_kb: 32 },
    cleanup_ignore: ['.*', '*.gitkeep'],
  };
  await fs.mkdir(TMP, { recursive: true });
  await fs.writeFile(path.join(TMP, 'config.json'), JSON.stringify(cfg, null, 2), 'utf-8');
}

let serverProc = null;

async function startServer(exe, mode) {
  await writeTempConfig(mode);
  await fs.writeFile(path.join(TMP, 'service.log'), '', 'utf-8');
  const logStream = (await import('fs')).createWriteStream(path.join(TMP, 'service.log'));
  serverProc = spawn(exe, [], { cwd: TMP, stdio: ['ignore', 'pipe', 'pipe'], windowsHide: true });
  serverProc.stdout.pipe(logStream);
  serverProc.stderr.pipe(logStream);

  const deadline = Date.now() + 30000;
  while (Date.now() < deadline) {
    try {
      const r = await http('GET', '/api/domains');
      if (r.status === 200) return;
    } catch {
      /* not ready */
    }
    await sleep(200);
  }
  throw new Error('server did not start within 30s');
}

async function stopServer() {
  if (!serverProc) return;
  serverProc.kill();
  await sleep(800);
  if (!serverProc.killed) serverProc.kill('SIGKILL');
  serverProc = null;
  // 等端口释放
  await sleep(500);
}

// ============ 内容与建域 ============
async function generateContent(domain) {
  const script = path.join(ROOT, 'scripts', 'generate_nested_md.py');
  const r = spawnSync('uv', ['run', 'python', script, '--domain', domain, '--size', 'small', '--clean'], {
    cwd: ROOT,
    encoding: 'utf-8',
    shell: true,
  });
  if (r.status !== 0) {
    throw new Error(`generate content failed for ${domain}: ${r.stderr || r.stdout}`);
  }
}

async function ensureDomain(domain) {
  let r = await http('POST', `/api/domain/${domain}`, { page_title: domain });
  if (r.status === 409) {
    await http('DELETE', `/api/domain/${domain}`, { delete_input: false, delete_output: true });
    r = await http('POST', `/api/domain/${domain}`, { page_title: domain });
  }
  assertTrue(r.status === 201, `create domain ${domain} -> ${r.status} ${r.text}`);
}

// ============ 任务观测 ============
async function getTasks() {
  const r = await http('GET', '/api/tasks');
  return r.json;
}

async function waitAllDone(timeoutMs) {
  const deadline = Date.now() + timeoutMs;
  while (Date.now() < deadline) {
    const t = await getTasks();
    if (t && t.count === 0) return;
    await sleep(1000);
  }
  throw new Error('builds did not finish in time');
}

async function assertBuildSucceeded(domain) {
  const s = await http('GET', `/api/domain/${domain}/status`);
  assertTrue(s.json?.status === 'idle', `${domain} should be idle, got ${JSON.stringify(s.json)}`);
  const log = await http('GET', `/api/domain/${domain}/logs`);
  assertTrue(log.text.includes('✅ 构建成功'), `${domain} build not successful; log tail: ${log.text.slice(-300)}`);
}

// ============ 场景 ============
async function createAllDomains() {
  for (const d of DOMAINS) await ensureDomain(d);
}

async function scenario(mode, expectConcurrent) {
  console.log(`\n=== 场景: build_mode=${mode} ===`);
  const exe = await buildServer();
  await startServer(exe, mode);

  await createAllDomains();

  // 同时触发 3 个构建
  const responses = await Promise.all(DOMAINS.map((d) => http('POST', `/api/domain/${d}/build?reset=true`)));
  const statuses = responses.map((r) => r.json?.status);
  console.log(`  触达响应: ${JSON.stringify(statuses)}`);

  // 立刻观察 /api/tasks
  const first = await getTasks();
  console.log(`  /api/tasks 首帧: count=${first?.count} running=${first?.running} queued=${first?.queued} buildMode=${first?.buildMode}`);
  assertTrue(first?.buildMode === mode, `buildMode should be ${mode}, got ${first?.buildMode}`);

  if (mode === 'serial') {
    const accepted = statuses.filter((s) => s === 'Accepted').length;
    const queued = statuses.filter((s) => s === 'Queued').length;
    assertTrue(accepted === 1 && queued === 2, `serial 期望 1 Accepted + 2 Queued，实际 ${JSON.stringify(statuses)}`);
    ok(`${mode}: 触发响应 1 Accepted + 2 Queued`);

    const queuedTask = (first?.tasks || []).find((t) => t.status === 'queued');
    assertTrue(queuedTask && queuedTask.queuePosition >= 1, `queued 任务应带 queuePosition，实际 ${JSON.stringify(queuedTask)}`);
    ok(`${mode}: /api/tasks 暴露排队状态与位置`, `queuePosition=${queuedTask.queuePosition}`);
  } else {
    const accepted = statuses.filter((s) => s === 'Accepted').length;
    assertTrue(accepted === 3, `parallel 期望 3 Accepted，实际 ${JSON.stringify(statuses)}`);
    ok(`${mode}: 触发响应 3 Accepted`);
  }

  // 轮询直到全部结束，记录 running 峰值
  let maxRunning = 0;
  let sawQueued = false;
  const deadline = Date.now() + 15 * 60 * 1000;
  while (Date.now() < deadline) {
    const t = await getTasks();
    if (t) {
      maxRunning = Math.max(maxRunning, t.running || 0);
      if ((t.queued || 0) > 0) sawQueued = true;
      if (t.count === 0) break;
    }
    await sleep(800);
  }

  if (mode === 'serial') {
    assertTrue(maxRunning <= 1, `serial 模式 running 峰值应 <=1，实际 ${maxRunning}`);
    assertTrue(sawQueued, 'serial 模式应观察到排队');
    ok(`${mode}: running 峰值<=1 且观察到排队`, `maxRunning=${maxRunning}`);
  } else {
    assertTrue(expectConcurrent <= maxRunning, `parallel 模式 running 峰值应 >=${expectConcurrent}，实际 ${maxRunning}`);
    ok(`${mode}: 恢复并发`, `maxRunning=${maxRunning}`);
  }

  // 全部成功
  for (const d of DOMAINS) await assertBuildSucceeded(d);
  ok(`${mode}: 3 个域全部构建成功`);

  await stopServer();
}

async function main() {
  try {
    // 生成内容（生成失败直接抛）
    console.log('生成业务域内容（uv run python generate_nested_md.py, size=small）...');
    for (const d of DOMAINS) {
      console.log(`  -> input/${d}`);
      await generateContent(d);
    }

    await scenario('serial', 1);
    await scenario('parallel', 2);

    const failed = results.filter((r) => r.status === 'FAIL');
    console.log(`\n结果：${results.length - failed.length}/${results.length} 通过，${failed.length} 失败`);
    if (!process.env.KEEP_TMP) {
      console.log(`产物保留在 ${TMP}（如需清理：Remove-Item -Recurse -Force ${TMP}）`);
    }
    process.exit(failed.length > 0 ? 1 : 0);
  } catch (err) {
    console.error('\nFATAL:', err.message);
    try {
      await stopServer();
    } catch {
      /* ignore */
    }
    process.exit(1);
  }
}

main();
