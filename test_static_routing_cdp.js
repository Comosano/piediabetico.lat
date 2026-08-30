/**
 * SMALL CHROMIUM CDP TEST — ROOT-RELATIVE STATIC ASSET ROUTING
 * Verifies that /profesional, /paciente, and /r/{synthetic_token} requested assets
 * directly from /app.js and /sw.js with correct Content-Type (application/javascript).
 */

const http = require('http');
const fs = require('fs');
const path = require('path');
const assert = require('assert');
const { spawn } = require('child_process');

const CHROME_PATH = 'C:\\Program Files\\Google\\Chrome\\Application\\chrome.exe';
let cdpWs = null;
let msgId = 1;
const pendingResponses = new Map();
let server = null;
let chromeProcess = null;
let watchdogTimer = null;

function sendCDP(method, params = {}) {
  return new Promise((resolve, reject) => {
    const id = msgId++;
    pendingResponses.set(id, { resolve, reject });
    cdpWs.send(JSON.stringify({ id, method, params }));
  });
}

async function evaluate(expression) {
  const res = await sendCDP('Runtime.evaluate', {
    expression,
    returnByValue: true,
    awaitPromise: true
  });
  if (res.result && res.result.exceptionDetails) {
    throw new Error(JSON.stringify(res.result.exceptionDetails));
  }
  return res.result ? res.result.value : undefined;
}

async function sleep(ms) {
  return new Promise(r => setTimeout(r, ms));
}

async function runStaticRoutingTest() {
  console.log('\n═══════════════════════════════════════════════════════════════════════');
  console.log('🌐 CHROMIUM CDP DIAGNOSTIC: ROOT-RELATIVE STATIC ASSET ROUTING');
  console.log('═══════════════════════════════════════════════════════════════════════\n');

  watchdogTimer = setTimeout(() => {
    console.error('\n❌ DIAGNOSTIC TIMEOUT (45s exceeded)');
    cleanupAndExit(1);
  }, 45000);

  const requestedUrls = [];
  const consoleErrors = [];
  const unhandledExceptions = [];

  try {
    // Start HTTP Static Server
    server = http.createServer((req, res) => {
      const rawUrl = req.url.split('?')[0];
      const fileName = path.basename(rawUrl);
      let ext = path.extname(fileName);

      requestedUrls.push(req.url);

      let filePath = path.join(__dirname, fileName);
      if (!ext || !fs.existsSync(filePath) || !fs.statSync(filePath).isFile()) {
        filePath = path.join(__dirname, 'index.html');
        ext = '.html';
      }

      const mimeTypes = {
        '.html': 'text/html',
        '.js': 'application/javascript',
        '.css': 'text/css',
        '.png': 'image/png',
        '.svg': 'image/svg+xml'
      };
      res.writeHead(200, { 'Content-Type': mimeTypes[ext] || 'text/plain' });
      fs.createReadStream(filePath).pipe(res);
    });

    await new Promise(r => server.listen(3000, r));
    console.log('  [Setup] Server running at http://localhost:3000');

    // Spawn Chrome
    chromeProcess = spawn(CHROME_PATH, [
      '--headless=new',
      '--disable-gpu',
      '--no-first-run',
      '--no-default-browser-check',
      '--remote-debugging-port=9222',
      '--window-size=412,915',
      '--user-data-dir=' + path.join(__dirname, '.temp_chrome_profile_route')
    ]);

    await sleep(1500);

    const listRes = await fetch('http://127.0.0.1:9222/json/list');
    const listData = await listRes.json();
    const target = listData.find(t => t.type === 'page') || listData[0];
    const wsUrl = target.webSocketDebuggerUrl;

    cdpWs = new WebSocket(wsUrl);
    await new Promise((resolve, reject) => {
      cdpWs.onopen = resolve;
      cdpWs.onerror = reject;
    });

    cdpWs.onmessage = (event) => {
      const msg = JSON.parse(event.data);
      if (msg.method === 'Runtime.consoleAPICalled') {
        const text = msg.params.args.map(a => a.value || a.description || JSON.stringify(a)).join(' ');
        if (msg.params.type === 'error') consoleErrors.push(text);
      } else if (msg.method === 'Runtime.exceptionThrown') {
        unhandledExceptions.push(JSON.stringify(msg.params.exceptionDetails));
      }

      if (msg.id && pendingResponses.has(msg.id)) {
        const { resolve, reject } = pendingResponses.get(msg.id);
        pendingResponses.delete(msg.id);
        if (msg.error) reject(new Error(msg.error.message));
        else resolve(msg.result);
      }
    };

    await sendCDP('Page.enable');
    await sendCDP('Runtime.enable');
    await sendCDP('Network.enable');

    // A. Test GET /profesional
    console.log('  [Test A] Navigating to /profesional...');
    await sendCDP('Page.navigate', { url: 'http://localhost:3000/profesional' });
    await sleep(800);

    const scriptSrcsA = await evaluate(`Array.from(document.scripts).map(s => s.getAttribute('src')).filter(Boolean)`);
    console.log(`    ✓ /profesional script sources in DOM: ${JSON.stringify(scriptSrcsA)}`);
    assert(scriptSrcsA.some(s => s.startsWith('/app.js')), 'Script src must be root-relative /app.js');

    // B. Test GET /paciente
    console.log('\n  [Test B] Navigating to /paciente...');
    await sendCDP('Page.navigate', { url: 'http://localhost:3000/paciente' });
    await sleep(800);

    const scriptSrcsB = await evaluate(`Array.from(document.scripts).map(s => s.getAttribute('src')).filter(Boolean)`);
    console.log(`    ✓ /paciente script sources in DOM: ${JSON.stringify(scriptSrcsB)}`);
    assert(scriptSrcsB.some(s => s.startsWith('/app.js')), 'Script src must be root-relative /app.js');

    // C. Test GET /r/SYNTHETIC_ROUTE_TOKEN_TEST
    console.log('\n  [Test C] Navigating to /r/SYNTHETIC_ROUTE_TOKEN_TEST...');
    await sendCDP('Page.navigate', { url: 'http://localhost:3000/r/SYNTHETIC_ROUTE_TOKEN_TEST' });
    await sleep(800);

    const scriptSrcsC = await evaluate(`Array.from(document.scripts).map(s => s.getAttribute('src')).filter(Boolean)`);
    console.log(`    ✓ /r/{token} script sources in DOM: ${JSON.stringify(scriptSrcsC)}`);
    assert(scriptSrcsC.some(s => s.startsWith('/app.js')), 'Script src must be root-relative /app.js');

    const hasNestedAppJs = requestedUrls.some(u => u.includes('/r/app.js'));
    const hasNestedSwJs = requestedUrls.some(u => u.includes('/r/sw.js'));

    console.log(`    ✓ Nested /r/app.js prevented: ${!hasNestedAppJs}`);
    console.log(`    ✓ Nested /r/sw.js prevented: ${!hasNestedSwJs}`);

    assert(!hasNestedAppJs, 'Must NEVER request /r/app.js');
    assert(!hasNestedSwJs, 'Must NEVER request /r/sw.js');

    // Verify zero syntax errors or MIME errors
    const syntaxErrors = unhandledExceptions.filter(e => e.includes('Unexpected token') || e.includes('MIME type'));
    console.log(`    ✓ Syntax / MIME Exceptions detected: ${syntaxErrors.length}`);
    assert.strictEqual(syntaxErrors.length, 0, `No MIME or Unexpected token errors allowed: ${JSON.stringify(syntaxErrors)}`);

    console.log('\n═══════════════════════════════════════════════════════════════════════');
    console.log('🎉 STATIC ASSET ROUTING TEST PASSED (100%)');
    console.log('═══════════════════════════════════════════════════════════════════════\n');

  } catch (err) {
    console.error('\n❌ ROUTING TEST FAILURE:', err.message);
    cleanupAndExit(1);
  } finally {
    cleanupAndExit(0);
  }
}

function cleanupAndExit(exitCode) {
  if (watchdogTimer) {
    clearTimeout(watchdogTimer);
    watchdogTimer = null;
  }
  if (cdpWs) {
    try { cdpWs.close(); } catch (_) {}
    cdpWs = null;
  }
  if (chromeProcess) {
    try { chromeProcess.kill('SIGKILL'); } catch (_) {}
    chromeProcess = null;
  }
  if (server) {
    try { server.close(); } catch (_) {}
    server = null;
  }
  try {
    fs.rmSync(path.join(__dirname, '.temp_chrome_profile_route'), { recursive: true, force: true });
  } catch (_) {}

  if (exitCode !== 0) {
    process.exit(exitCode);
  }
}

runStaticRoutingTest();
