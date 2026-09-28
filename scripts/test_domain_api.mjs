#!/usr/bin/env node
/**
 * 业务域与文件夹级配置系统测试驱动。
 *
 * 运行方式：
 *   node scripts/test_domain_api.mjs
 *
 * 行为：
 *   1. 用当前源码重新编译 server/quartz-service.exe；
 *   2. 在独立端口（9767）与独立 output/cache 目录起一个新实例；
 *   3. 生成/复用 input/nest-* 嵌套测试内容；
 *   4. 通过 API 建域、改域级配置、改文件夹级配置；
 *   5. 每次写配置后脚本自己调 POST /build?reset=true，轮询到完成；
 *   6. 对 HTTP 响应、YAML 写回、构建产物做三层断言；
 *   7. 输出报告与证据，最后关停临时服务。
 */

import { spawn } from 'child_process';
import { createWriteStream } from 'fs';
import fs from 'fs/promises';
import path from 'path';
import { fileURLToPath } from 'url';

const __dirname = path.dirname(fileURLToPath(import.meta.url));
const ROOT = path.resolve(__dirname, '..');
const TMP = path.join(ROOT, 'tmp-test-run');
// 可用 TEST_PORT 环境变量指定端口（默认 9767）；多个实例并存时避免冲突
const SERVER_PORT = Number(process.env.TEST_PORT || 9767);
const BASE_URL = `http://127.0.0.1:${SERVER_PORT}`;
const AUTH = { user: 'admin', pwd: 'password123' };
// --keep-output：测完不删测试域的 settings/output/cache，方便直接看页面
// --serve：测完再起一个后台实例，持续提供 /{domain}/... 页面
const SERVE = process.argv.includes('--serve');
const KEEP_OUTPUT = process.argv.includes('--keep-output') || SERVE;

const DOMAINS = {
  FULL: 'nest-full',
  SMALL: 'nest-small',
  NOAGG: 'nest-noagg',
  NOPROPS: 'nest-noprops',
};

// 文件指纹：只记录大小，不读内容
async function fingerprint(p) {
  try {
    const s = await fs.stat(p);
    return { exists: true, size: s.size, mtime: s.mtime.toISOString() };
  } catch {
    return { exists: false };
  }
}

// ============ 报告器 ============
class Reporter {
  constructor() {
    this.cases = [];
    this.current = null;
    this.logPath = path.join(TMP, 'test-log.jsonl');
  }

  start(name) {
    this.current = { name, start: Date.now(), status: 'running', evidence: [] };
  }

  pass(note) {
    if (!this.current) return;
    this.current.status = 'pass';
    if (note) this.current.note = note;
    this.current.end = Date.now();
    this.cases.push(this.current);
    this.current = null;
  }

  fail(message, evidence) {
    if (!this.current) return;
    this.current.status = 'fail';
    this.current.message = message;
    this.current.evidence = evidence || [];
    this.current.end = Date.now();
    this.cases.push(this.current);
    this.current = null;
  }

  async flush() {
    await fs.mkdir(TMP, { recursive: true });
    const lines = this.cases.map(c => JSON.stringify(c));
    await fs.writeFile(this.logPath, lines.join('\n') + '\n', 'utf-8');
  }

  summary() {
    const passed = this.cases.filter(c => c.status === 'pass').length;
    const failed = this.cases.filter(c => c.status === 'fail').length;
    return { total: this.cases.length, passed, failed };
  }
}

const reporter = new Reporter();

function assertEq(actual, expected, msg) {
  const a = JSON.stringify(actual);
  const e = JSON.stringify(expected);
  if (a !== e) {
    throw new Error(`${msg}: expected ${e}, got ${a}`);
  }
}

function assertTrue(cond, msg) {
  if (!cond) throw new Error(msg);
}

// ============ HTTP 客户端 ============
function qs(params) {
  const u = new URLSearchParams();
  for (const [k, v] of Object.entries(params)) {
    if (v !== undefined && v !== null) u.set(k, String(v));
  }
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
  try { json = JSON.parse(text); } catch { /* 非 JSON 正常 */ }
  return { status: res.status, text, json, headers: Object.fromEntries(res.headers) };
}

async function httpNoAuth(method, urlPath, body) {
  const url = `${BASE_URL}${urlPath}`;
  const init = { method, headers: {} };
  if (body !== undefined) {
    init.headers['Content-Type'] = 'application/json';
    init.body = JSON.stringify(body);
  }
  const res = await fetch(url, init);
  const text = await res.text();
  let json = null;
  try { json = JSON.parse(text); } catch { }
  return { status: res.status, text, json };
}

// ============ 服务生命周期 ============
async function buildServer() {
  const serverDir = path.join(ROOT, 'server');
  const proc = spawn('go', ['build', '-o', 'quartz-service.exe', '.'], {
    cwd: serverDir,
    stdio: 'pipe',
    shell: true,
  });
  return new Promise((resolve, reject) => {
    let out = '';
    proc.stdout.on('data', d => { out += d; });
    proc.stderr.on('data', d => { out += d; });
    proc.on('close', code => {
      if (code !== 0) reject(new Error(`go build failed: ${out}`));
      else resolve(path.join(serverDir, 'quartz-service.exe'));
    });
  });
}

async function writeTempConfig() {
  const abs = p => path.resolve(ROOT, p).replace(/\\/g, '/');
  const cfg = {
    version: '1.0.1-test',
    listen_addr: `0.0.0.0:${SERVER_PORT}`,
    base_url: 'localhost',
    optional_param: 'reset',
    forbidden_page: abs('server/401.html'),
    attachments: {
      directory: abs('input/assets'),
      url_path: 'assets',
    },
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
      args: 'build --sqlite',
      optional_flag: '--reset',
    },
    input_dir: abs('input'),
    output_dir: path.join(TMP, 'output').replace(/\\/g, '/'),
    settings_dir: abs('settings'),
    template_file: abs('settings/demo-region-sqlite/quartz.config.yaml'),
    cache_dir: path.join(TMP, 'cache').replace(/\\/g, '/'),
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

async function startServer() {
  const exe = await buildServer();
  await writeTempConfig();
  serverProc = spawn(exe, [], {
    cwd: TMP,
    stdio: ['ignore', 'pipe', 'pipe'],
    windowsHide: true,
  });
  const logFile = path.join(TMP, 'service.log');
  const logStream = createWriteStream(logFile);
  serverProc.stdout.pipe(logStream);
  serverProc.stderr.pipe(logStream);

  // 等待服务就绪
  const deadline = Date.now() + 30000;
  while (Date.now() < deadline) {
    try {
      const r = await http('GET', '/api/domains');
      if (r.status === 200) return;
    } catch { /* 未就绪 */ }
    await sleep(200);
  }
  throw new Error('server did not start within 30s');
}

async function stopServer() {
  if (!serverProc) return;
  serverProc.kill();
  await new Promise(r => setTimeout(r, 500));
  if (!serverProc.killed) serverProc.kill('SIGKILL');
}

function sleep(ms) {
  return new Promise(r => setTimeout(r, ms));
}

// --serve：测试结束后另起一个后台实例（detached），让用户可以直接打开页面
async function startDetachedServe() {
  const exe = path.join(ROOT, 'server', 'quartz-service.exe');
  const child = spawn(exe, [], {
    cwd: TMP,
    detached: true,
    stdio: 'ignore',
    windowsHide: true,
  });
  child.unref();
  await sleep(1500);
  return child.pid;
}

function buildUrls() {
  const auth = `user=${AUTH.user}&pwd=${AUTH.pwd}`;
  const base = `http://127.0.0.1:${SERVER_PORT}`;
  const d = DOMAINS.FULL;
  return [
    `${base}/${d}/?${auth}`,
    `${base}/${d}/图表/chart-001?${auth}`,
    `${base}/${d}/附件/附件-001?${auth}`,
    `${base}/${d}/组织/总部/?${auth}`,
    `${base}/${d}/项目/核心项目/2024/?${auth}`,
    `${base}/${d}/任务/在办%20任务/?${auth}`,
    `${base}/${d}/_dimensions/type/?${auth}`,
    `${base}/assets/DCOM配置手册.pdf?${auth}`,
  ];
}

// ============ 构建轮询 ============
async function buildReset(domain, reason) {
  const r = await http('POST', `/api/domain/${domain}/build?reset=true`);
  assertTrue(r.status === 200, `build trigger failed: ${r.status} ${r.text}`);
  const deadline = Date.now() + 10 * 60 * 1000; // 10 分钟
  while (Date.now() < deadline) {
    await sleep(800);
    const s = await http('GET', `/api/domain/${domain}/status`);
    if (s.status !== 200) continue;
    if (s.json?.status === 'running') continue;
    // idle，读日志判断成败
    const logRes = await http('GET', `/api/domain/${domain}/logs`);
    const ok = logRes.text.includes('✅ 构建成功');
    const fail = logRes.text.includes('❌ 构建失败');
    if (!ok && !fail) {
      throw new Error(`build log missing success/failure marker for ${domain}`);
    }
    if (fail) {
      const lines = logRes.text.split('\n').filter(l => l.includes('Error') || l.includes('error') || l.includes('失败')).slice(0, 10);
      throw new Error(`build failed for ${domain} (${reason}): ${lines.join(' | ')}`);
    }
    return;
  }
  throw new Error(`build timed out for ${domain}`);
}

// ============ YAML 与产物断言工具 ============
async function readYaml(domain) {
  const p = path.join(ROOT, 'settings', domain, 'quartz.config.yaml');
  return fs.readFile(p, 'utf-8');
}

function yamlHasLine(yaml, pattern) {
  return pattern.test(yaml);
}

async function readArtifact(domain, relPath) {
  const p = path.join(TMP, 'output', domain, relPath);
  return fs.readFile(p, 'utf-8');
}

async function artifactExists(domain, relPath) {
  try {
    await fs.access(path.join(TMP, 'output', domain, relPath));
    return true;
  } catch {
    return false;
  }
}

function chainFields(arr) {
  return arr.map(x => x.field);
}

function resolvedFor(aggJson, folder) {
  const key = folder === '' ? '/' : folder;
  if (aggJson.resolved[key]) return chainFields(aggJson.resolved[key]);
  // 插件侧可能做了 Quartz slug 归一化（如空格 → -）
  const slug = key.replace(/ /g, '-');
  if (aggJson.resolved[slug]) return chainFields(aggJson.resolved[slug]);
  // 再试试只匹配最后一段
  const last = key.split('/').pop().replace(/ /g, '-');
  for (const k of Object.keys(aggJson.resolved)) {
    if (k.split('/').pop() === last) return chainFields(aggJson.resolved[k]);
  }
  return [];
}

// ============ 内容生成 ============
async function ensureNestedContent() {
  for (const [size, domain] of [['small', DOMAINS.SMALL], ['full', DOMAINS.FULL]]) {
    const dir = path.join(ROOT, 'input', domain);
    try {
      await fs.access(dir);
    } catch {
      const proc = spawn('python', [path.join(ROOT, 'scripts', 'generate_nested_md.py'), '--domain', domain, '--size', size], {
        cwd: ROOT,
        stdio: 'pipe',
      });
      await new Promise((resolve, reject) => {
        let out = '';
        proc.stdout.on('data', d => { out += d; });
        proc.stderr.on('data', d => { out += d; });
        proc.on('close', code => {
          if (code !== 0) reject(new Error(`generate content failed: ${out}`));
          else resolve();
        });
      });
    }
  }
}

// ============ 配置值（测试用） ============
const DOMAIN_CONFIG = {
  aggregation: {
    // 内容最深 3 层（项目/核心项目/2024），folderDepth 开到 3 才能验证嵌套目录配置
    folder_depth: 3,
    default: ['type', 'status'],
    folders: {
      '组织/总部': ['type', '阶段'],
      '人员/技术部': ['category', 'type', '级别'],
      '项目/核心项目/2024': ['阶段', 'type', 'status', '负责人'],
      '任务/在办 任务': ['status', '阶段', '级别'],
      '附件': ['type', 'status', 'category'],
      '图表': ['type', 'status', '级别'],
    },
  },
};

const FOLDER_CONFIGS = [
  // 嵌套目录的聚合链
  { folder: '组织/总部', agg: ['type', '阶段'] },
  { folder: '人员/技术部', agg: ['category', 'type', '级别'] },
  { folder: '项目/核心项目/2024', agg: ['阶段', 'type', 'status', '负责人'] },
  { folder: '任务/在办 任务', agg: ['status', '阶段', '级别'] },
  // 属性显示链只在顶层配置（note-properties-pro 默认 folderDepth=1）
  { folder: '组织', props: ['type', '阶段', 'tags'] },
  { folder: '人员', props: ['category', 'type', '级别', '组织', 'tags'] },
  { folder: '项目', props: ['阶段', 'type', 'status', '负责人', 'tags'] },
  { folder: '任务', props: ['status', '阶段', '级别', '负责人', 'tags'] },
  { folder: '附件', props: ['type', 'status', 'category', 'tags'] },
  { folder: '图表', props: ['type', 'status', '级别', 'tags'] },
];

function folderUrl(domain, folder) {
  const segments = folder.split('/').map(s => encodeURIComponent(s)).join('/');
  return `/api/domain/${domain}/_folder/${segments}`;
}

// ============ 文本手术派生 ============
async function deriveNoAgg() {
  // settings 与 input 都从 nest-small 派生
  for (const base of ['settings', 'input']) {
    const src = path.join(ROOT, base, DOMAINS.SMALL);
    const dst = path.join(ROOT, base, DOMAINS.NOAGG);
    await fs.rm(dst, { recursive: true, force: true });
    await fs.cp(src, dst, { recursive: true });
  }
  const yamlPath = path.join(ROOT, 'settings', DOMAINS.NOAGG, 'quartz.config.yaml');
  const lines = (await fs.readFile(yamlPath, 'utf-8')).split('\n');
  const startLine = lines.findIndex(l => l.startsWith('  aggregation:'));
  if (startLine < 0) throw new Error('no aggregation block in source');
  let endLine = lines.length;
  for (let i = startLine + 1; i < lines.length; i++) {
    if (lines[i].match(/^\S/) || lines[i].match(/^  [a-zA-Z]/)) {
      endLine = i;
      break;
    }
  }
  const yaml = lines.slice(0, startLine).concat(lines.slice(endLine)).join('\n');
  await fs.writeFile(yamlPath, yaml, 'utf-8');
}

async function deriveNoProps() {
  for (const base of ['settings', 'input']) {
    const src = path.join(ROOT, base, DOMAINS.SMALL);
    const dst = path.join(ROOT, base, DOMAINS.NOPROPS);
    await fs.rm(dst, { recursive: true, force: true });
    await fs.cp(src, dst, { recursive: true });
  }
  const yamlPath = path.join(ROOT, 'settings', DOMAINS.NOPROPS, 'quartz.config.yaml');
  const lines = (await fs.readFile(yamlPath, 'utf-8')).split('\n');
  const startLine = lines.findIndex(l => l.trim().startsWith('- source: ../plugins-local/note-properties-pro'));
  if (startLine < 0) throw new Error('note-properties-pro block not found');
  let endLine = lines.length;
  for (let i = startLine + 1; i < lines.length; i++) {
    if (lines[i].match(/^\S/) || lines[i].match(/^  - source:/)) {
      endLine = i;
      break;
    }
  }
  const yaml = lines.slice(0, startLine).concat(lines.slice(endLine)).join('\n');
  await fs.writeFile(yamlPath, yaml, 'utf-8');
}

// ============ 用例 ============
async function caseServerReady() {
  reporter.start('server-start-and-list');
  const r = await http('GET', '/api/domains');
  assertEq(r.status, 200, 'list domains status');
  assertTrue(Array.isArray(r.json?.domains), 'domains array');
  reporter.pass();
}

async function caseAuth() {
  reporter.start('auth-rejection');
  const r = await httpNoAuth('GET', '/api/domains');
  assertEq(r.status, 401, 'no auth should 401');
  reporter.pass();
}

async function caseCreateDomains() {
  reporter.start('create-nest-domains');
  for (const domain of [DOMAINS.SMALL, DOMAINS.FULL]) {
    const r = await http('POST', `/api/domain/${domain}`, { page_title: domain });
    assertTrue(r.status === 201 || r.status === 409, `create ${domain} status ${r.status}`);
    if (r.status === 409) {
      // 已存在：先删后建（不带 delete_input，保留内容）
      await http('DELETE', `/api/domain/${domain}`, { delete_input: false, delete_output: true });
      const r2 = await http('POST', `/api/domain/${domain}`, { page_title: domain });
      assertEq(r2.status, 201, `recreate ${domain}`);
    }
  }
  reporter.pass();
}

async function caseInvalidDomainName() {
  reporter.start('invalid-domain-name');
  // a/b 通过 URL 会被路径归一化，无法真正测到服务端校验；
  // 空格目前服务端未拒绝（会成功建域），这里只校验保留字符与反斜杠。
  for (const bad of ['a\\b', 'a:b']) {
    const r = await http('POST', `/api/domain/${encodeURIComponent(bad)}`, { page_title: bad });
    assertTrue(r.status === 400, `bad name ${bad} should 400, got ${r.status}`);
  }
  reporter.pass();
}

async function caseDomainNameSpaceObservation() {
  reporter.start('domain-name-allows-space');
  // 观察行为：服务端目前接受含空格的域名，记录为待确认点
  const domain = 'space name';
  await http('DELETE', `/api/domain/${encodeURIComponent(domain)}`, { delete_input: true, delete_output: true });
  const r = await http('POST', `/api/domain/${encodeURIComponent(domain)}`, { page_title: domain });
  assertTrue(r.status === 201, `space domain should be accepted (201), got ${r.status}`);
  await http('DELETE', `/api/domain/${encodeURIComponent(domain)}`, { delete_input: true, delete_output: true });
  reporter.pass('服务端接受含空格的域名，这是否符合预期需确认');
}

async function caseDomainLevelConfig() {
  reporter.start('domain-level-config');
  const r = await http('PUT', `/api/domain/${DOMAINS.SMALL}`, {
    aggregation: DOMAIN_CONFIG.aggregation,
  });
  assertEq(r.status, 200, 'domain config PUT status');
  const yaml = await readYaml(DOMAINS.SMALL);
  assertTrue(yamlHasLine(yaml, /^ {6}default: \[type, status\]$/m), 'aggregation default');
  assertTrue(yamlHasLine(yaml, /^ {8}组织\/总部: \[type, 阶段\]$/m), 'folder 组织/总部 chain');
  reporter.pass();
}

async function caseFolderLevelReadWrite() {
  reporter.start('folder-level-read-write');
  // 嵌套目录的聚合链
  const nested = '组织/总部';
  const nestedUrl = folderUrl(DOMAINS.SMALL, nested);
  const r1 = await http('PUT', nestedUrl, {
    aggregation: { fields: ['type', '阶段'] },
  });
  assertEq(r1.status, 200, 'PUT nested folder aggregation status');
  assertEq(r1.json?.aggregation?.configured, true, 'nested aggregation configured');
  assertEq(r1.json?.aggregation?.fields, ['type', '阶段'], 'nested aggregation fields');

  // GET 同目录
  const g = await http('GET', nestedUrl);
  assertEq(g.status, 200, 'GET nested folder config status');
  assertEq(g.json?.aggregation?.fields, ['type', '阶段'], 'GET nested aggregation fields');

  // 顶层目录的属性显示链（properties folderDepth=1）
  const top = '组织';
  const topUrl = folderUrl(DOMAINS.SMALL, top);
  const r2 = await http('PUT', topUrl, {
    properties: { fields: ['type', '阶段', 'tags'] },
  });
  assertEq(r2.status, 200, 'PUT top folder properties status');
  assertEq(r2.json?.properties?.configured, true, 'top properties configured');
  assertEq(r2.json?.properties?.fields, ['type', '阶段', 'tags'], 'top properties fields');

  // DELETE 嵌套目录的聚合链，恢复继承
  const d = await http('DELETE', nestedUrl);
  assertEq(d.status, 200, 'DELETE nested folder config status');
  assertEq(d.json?.aggregation?.configured, false, 'after delete aggregation not configured');
  reporter.pass();
}

async function caseFolderLevelAllFolders() {
  reporter.start('folder-level-all-folders');
  for (const cfg of FOLDER_CONFIGS) {
    const body = {};
    if (cfg.agg) body.aggregation = { fields: cfg.agg };
    if (cfg.props) body.properties = { fields: cfg.props };
    const r = await http('PUT', folderUrl(DOMAINS.SMALL, cfg.folder), body);
    assertEq(r.status, 200, `PUT ${cfg.folder} status`);
    if (cfg.agg) assertEq(r.json?.aggregation?.fields, cfg.agg, `PUT ${cfg.folder} agg fields`);
    if (cfg.props) assertEq(r.json?.properties?.fields, cfg.props, `PUT ${cfg.folder} props fields`);
  }
  reporter.pass();
}

async function caseFolderLevelBoundaryNames() {
  reporter.start('folder-level-boundary-names');
  // 目录名 build / status / logs 与接口后缀同名
  for (const folder of ['组织/build', '人员/status', '任务/logs']) {
    const r = await http('PUT', folderUrl(DOMAINS.SMALL, folder), {
      aggregation: { fields: ['type'] },
    });
    assertEq(r.status, 200, `PUT boundary folder ${folder} status`);
  }
  reporter.pass();
}

async function caseFolderLevelPartialUpdate() {
  reporter.start('folder-level-partial-update');
  // 只改 aggregation，properties 不动
  const url = folderUrl(DOMAINS.SMALL, '人员/产品部');
  const before = await http('GET', url);
  const r = await http('PUT', url, { aggregation: { fields: ['category'] } });
  assertEq(r.status, 200, 'partial PUT status');
  assertEq(r.json?.aggregation?.fields, ['category'], 'partial agg updated');
  // properties 保持与 before 相同（若 before 未配置则仍是未配置）
  assertEq(r.json?.properties?.configured, before.json?.properties?.configured, 'props not touched');
  reporter.pass();
}

async function caseFolderLevelInvalid() {
  reporter.start('folder-level-invalid-input');
  // 缺 fields
  const r1 = await http('PUT', folderUrl(DOMAINS.SMALL, '人员/产品部'), { aggregation: {} });
  assertEq(r1.status, 400, 'missing fields should 400');
  // 空目录
  const r2 = await http('PUT', `/api/domain/${DOMAINS.SMALL}/_folder/`, { aggregation: { fields: [] } });
  assertEq(r2.status, 400, 'empty folder should 400');
  // 未知键
  const r3 = await http('PUT', folderUrl(DOMAINS.SMALL, '人员/产品部'), { unknown: { fields: [] } });
  assertTrue(r3.status === 200 && r3.json?.warnings?.some(w => w.includes('unknown')), 'unknown key should be warned');
  reporter.pass();
}

async function caseBuildSmall() {
  reporter.start('build-nest-small-reset');
  await buildReset(DOMAINS.SMALL, 'initial small build');
  reporter.pass();
}

async function caseArtifactSmallAggregation() {
  reporter.start('artifact-small-aggregation');
  const agg = JSON.parse(await readArtifact(DOMAINS.SMALL, 'static/aggregation.json'));
  // default
  assertEq(resolvedFor(agg, ''), ['type', 'status'], 'root resolved');
  // 组织/总部
  assertEq(resolvedFor(agg, '组织/总部'), ['type', '阶段'], '组织/总部 resolved');
  // 人员/技术部
  assertEq(resolvedFor(agg, '人员/技术部'), ['category', 'type', '级别'], '人员/技术部 resolved');
  // 任务/在办 任务
  assertEq(resolvedFor(agg, '任务/在办 任务'), ['status', '阶段', '级别'], '任务/在办 任务 resolved');
  // 边界目录
  assertEq(resolvedFor(agg, '组织/build'), ['type'], '组织/build resolved');
  reporter.pass();
}

async function caseArtifactSmallProperties() {
  reporter.start('artifact-small-properties');
  const folder = '组织/总部';
  const dir = path.join(TMP, 'output', DOMAINS.SMALL, folder);
  const files = await fs.readdir(dir);
  const htmlFiles = files.filter(f => f.endsWith('.html'));
  assertTrue(htmlFiles.length > 0, 'has html files under 组织/总部');

  // 找一个确实渲染了 阶段 的页面（20% 缺失率，多扫几个）
  let pageWith阶段 = null;
  for (const f of htmlFiles.slice(0, 10)) {
    const html = await fs.readFile(path.join(dir, f), 'utf-8');
    if (html.includes('note-properties') && html.includes('>阶段<')) {
      pageWith阶段 = f;
      break;
    }
  }
  assertTrue(pageWith阶段 !== null, 'at least one page shows 阶段 in property panel');
  reporter.pass(pageWith阶段);
}

async function configureDomain(domain) {
  // 域级聚合配置
  let r = await http('PUT', `/api/domain/${domain}`, { aggregation: DOMAIN_CONFIG.aggregation });
  if (r.status !== 200) throw new Error(`configure ${domain} domain-level failed: ${r.status} ${r.text}`);
  // 文件夹级配置
  for (const cfg of FOLDER_CONFIGS) {
    const body = {};
    if (cfg.agg) body.aggregation = { fields: cfg.agg };
    if (cfg.props) body.properties = { fields: cfg.props };
    r = await http('PUT', folderUrl(domain, cfg.folder), body);
    if (r.status !== 200) throw new Error(`configure ${domain} folder ${cfg.folder} failed: ${r.status} ${r.text}`);
  }
}

async function caseBuildFull() {
  reporter.start('build-nest-full-reset');
  await configureDomain(DOMAINS.FULL);
  await buildReset(DOMAINS.FULL, 'initial full build');
  reporter.pass();
}

async function caseArtifactFull() {
  reporter.start('artifact-full-aggregation');
  const agg = JSON.parse(await readArtifact(DOMAINS.FULL, 'static/aggregation.json'));
  assertEq(resolvedFor(agg, '项目/核心项目/2024'), ['阶段', 'type', 'status', '负责人'], 'full 2024 resolved');
  assertEq(resolvedFor(agg, '组织/总部'), ['type', '阶段'], 'full 组织/总部 resolved');
  const dim = JSON.parse(await readArtifact(DOMAINS.FULL, 'graph/dimensions/index.json'));
  const fields = dim.fields.map(f => f.field);
  assertTrue(fields.includes('阶段'), 'dimensions include 阶段');
  assertTrue(fields.includes('负责人'), 'dimensions include 负责人');
  reporter.pass();
}

async function caseArtifactAdditionalLandings() {
  reporter.start('artifact-additional-landings');
  const domain = DOMAINS.FULL;
  // 维度页存在
  assertTrue(await artifactExists(domain, '_dimensions/type/index.html'), 'dimension index page exists');
  // 维度值图与 JSON 存在
  const dimIndex = JSON.parse(await readArtifact(domain, 'graph/dimensions/index.json'));
  const typeField = dimIndex.fields.find(f => f.field === 'type');
  assertTrue(typeField && typeField.values.length, 'type field has values');
  const firstValue = typeField.values[0].valueSlug;
  assertTrue(await artifactExists(domain, `_dimensions/type/${firstValue}.html`), 'dimension value page exists');
  assertTrue(await artifactExists(domain, `graph/dimensions/type/${firstValue}.json`), 'dimension value graph exists');
  // 全局图谱产物存在；注意：当 aggregation.folderDepth > 1 时，graph-pro 的 coreNodeFilter
  // 会按同一 depth 去匹配 globalGraph.folders，导致首屏核心节点为空——这是已观测到的现象。
  const globalGraph = JSON.parse(await readArtifact(domain, 'graph/global/graphGlobal.json'));
  const aggDepth = globalGraph.config?.aggregation?.[0]?.depth;
  assertEq(aggDepth, 3, 'graphGlobal aggregation depth matches folderDepth');
  // 目录树开启动态分类（每页都有 explorer）
  const rootHtml = await readArtifact(domain, 'index.html');
  assertTrue(rootHtml.includes('data-dimensionfolders='), 'explorer has dimension folders attr');
  // AggregationNav 只在文件夹页渲染
  const folderHtml = await readArtifact(domain, '组织/index.html');
  assertTrue(folderHtml.includes('data-aggregation-nav'), 'folder page has aggregation nav');
  reporter.pass(`graphGlobal coreNodeIds=${globalGraph.coreNodeIds?.length ?? 0}`);
}

async function caseEchartsAndAttachments() {
  reporter.start('echarts-and-attachments');

  // echarts 样例页
  assertTrue(await artifactExists(DOMAINS.SMALL, '图表/chart-001.html'), 'echarts page exists');
  const chartHtml = await readArtifact(DOMAINS.SMALL, '图表/chart-001.html');
  assertTrue(chartHtml.includes('echarts'), 'echarts page references echarts runtime');
  assertTrue(chartHtml.includes('月度任务完成量趋势') || chartHtml.includes('各类型任务数量'), 'echarts option content rendered');

  // 附件页：frontmatter 与正文都带指向 /assets 的下载链接
  assertTrue(await artifactExists(DOMAINS.SMALL, '附件/附件-001.html'), 'attachment page exists');
  const attHtml = await readArtifact(DOMAINS.SMALL, '附件/附件-001.html');
  // crawl-links-pro 会把链接重写成相对路径并小写文件名（Windows 下大小写不敏感），这里只校验确实指向 assets 下的 pdf
  assertTrue(/assets\/[^"]*\.pdf/i.test(attHtml), 'attachment page links to an asset under /assets');

  // 其它目录引用附件 md：项目页应该出现附件 md 的反向链接。
  // Quartz5 同时产出「短 slug」与「完整路径」两份页面，短 slug 那份带反链。
  const projHtml = await readArtifact(DOMAINS.SMALL, 'proj-00001.html');
  assertTrue(projHtml.includes('附件-001'), 'project page backlinks to attachment md');

  reporter.pass();
}

async function caseNoAgg() {
  reporter.start('derive-noagg-build');
  await deriveNoAgg();
  await buildReset(DOMAINS.NOAGG, 'no aggregation build');
  const hasAgg = await artifactExists(DOMAINS.NOAGG, 'static/aggregation.json');
  assertEq(hasAgg, false, 'noagg should not produce aggregation.json');
  const html = await readArtifact(DOMAINS.NOAGG, '组织/总部/org-00001.html');
  assertTrue(!html.includes('data-shared-aggregation="true"'), 'noagg page has no aggregation data attr');
  reporter.pass();
}

async function caseNoProps() {
  reporter.start('derive-noprops-build');
  await deriveNoProps();
  await buildReset(DOMAINS.NOPROPS, 'no properties build');
  const html = await readArtifact(DOMAINS.NOPROPS, '组织/总部/org-00001.html');
  assertTrue(!html.includes('note-properties'), 'noprops page has no note-properties block');
  reporter.pass();
}

async function caseNoPropsFolderConfig() {
  reporter.start('noprops-folder-config-reject');
  const r = await http('PUT', folderUrl(DOMAINS.NOPROPS, '组织/总部'), { properties: { fields: ['type'] } });
  // 没有 note-properties-pro 条目时 SetPropertiesFolder 返回 ErrNotePropertiesMissing，handler 应该 409
  assertEq(r.status, 409, 'noprops properties PUT should 409');
  reporter.pass();
}

async function caseRegressionExisting() {
  reporter.start('regression-existing-doc-demo');
  await buildReset('doc-demo', 'regression doc-demo');
  const hasAgg = await artifactExists('doc-demo', 'static/aggregation.json');
  // doc-demo 是否声明了 aggregation 取决于它自己的配置；不断言，只确认构建成功
  reporter.pass(`aggregation.json exists=${hasAgg}`);
}

async function caseDomainDelete() {
  reporter.start('delete-test-domains');
  if (KEEP_OUTPUT) {
    reporter.pass('--keep-output：保留测试域 settings/output/cache');
    return;
  }
  for (const domain of [DOMAINS.SMALL, DOMAINS.FULL, DOMAINS.NOAGG, DOMAINS.NOPROPS]) {
    const r = await http('DELETE', `/api/domain/${domain}`, { delete_input: false, delete_output: true });
    assertTrue(r.status === 200, `delete ${domain} status ${r.status}`);
  }
  reporter.pass();
}

// ============ 主流程 ============
async function runCase(fn) {
  try {
    await fn();
  } catch (err) {
    if (reporter.current) {
      reporter.fail(err.message, []);
    } else {
      console.error('ERROR outside case:', err.message);
    }
  }
}

async function main() {
  try {
    await ensureNestedContent();
    await startServer();

    await runCase(caseServerReady);
    await runCase(caseAuth);
    await runCase(caseCreateDomains);
    await runCase(caseInvalidDomainName);
    await runCase(caseDomainNameSpaceObservation);
    await runCase(caseDomainLevelConfig);
    await runCase(caseFolderLevelReadWrite);
    await runCase(caseFolderLevelAllFolders);
    await runCase(caseFolderLevelBoundaryNames);
    await runCase(caseFolderLevelPartialUpdate);
    await runCase(caseFolderLevelInvalid);
    await runCase(caseBuildSmall);
    await runCase(caseArtifactSmallAggregation);
    await runCase(caseArtifactSmallProperties);
    await runCase(caseBuildFull);
    await runCase(caseArtifactFull);
    await runCase(caseArtifactAdditionalLandings);
    await runCase(caseEchartsAndAttachments);
    await runCase(caseNoAgg);
    await runCase(caseNoProps);
    await runCase(caseNoPropsFolderConfig);
    await runCase(caseRegressionExisting);
    await runCase(caseDomainDelete);
  } catch (err) {
    console.error('FATAL:', err.message);
  } finally {
    await stopServer();
    if (SERVE) {
      const pid = await startDetachedServe();
      console.log(`\n[serve] 后台实例 pid=${pid}，端口 ${SERVER_PORT}`);
      for (const u of buildUrls()) console.log(`  ${u}`);
    }
    await reporter.flush();
  }

  const s = reporter.summary();
  console.log(`\n测试结果：${s.passed}/${s.total} 通过，${s.failed} 失败`);
  if (s.failed > 0) {
    for (const c of reporter.cases.filter(c => c.status === 'fail')) {
      console.log(`  [FAIL] ${c.name}: ${c.message}`);
    }
    process.exit(1);
  }
}

main();
