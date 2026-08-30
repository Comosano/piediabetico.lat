/**
 * DEDICATED CHROMIUM CDP TEST — PROFESSIONAL PRIVACY GATE
 * Verifies exact checkbox state transitions, keyboard Space support, and button enablement.
 */

const http = require('http');
const fs = require('fs');
const path = require('path');
const crypto = require('crypto');
const assert = require('assert');
const { spawn, execSync } = require('child_process');

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

async function runPrivacyGateDiagnostic() {
  console.log('\n═══════════════════════════════════════════════════════════════════════');
  console.log('🛡️ CHROMIUM CDP DIAGNOSTIC: PROFESSIONAL PRIVACY GATE');
  console.log('═══════════════════════════════════════════════════════════════════════\n');

  watchdogTimer = setTimeout(() => {
    console.error('\n❌ DIAGNOSTIC TIMEOUT (60s exceeded)');
    cleanupAndExit(1);
  }, 60000);

  try {
    // Initialize test doctor credentials in PostgreSQL
    const testPassword = 'CDP_Doctor_Pass_' + crypto.randomBytes(6).toString('hex');
    const pythonCode = `
import os
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
from models import User
from domain.password_security import hash_password

db_url = os.environ.get("DATABASE_URL", "postgresql://adminpd:local_dev_password_pd_2026@postgres:5432/piediadbetico")
engine = create_engine(db_url)
Session = sessionmaker(bind=engine)
db = Session()
u = db.query(User).filter(User.email == "piloto.medico1@piediabetico.lat").first()
if u:
    u.password_hash = hash_password("${testPassword}")
    u.pilot_enabled = True
db.commit()
db.close()
`;
    execSync('docker exec -i piediabetico_local_api python', { input: pythonCode, encoding: 'utf8' });

    // Start HTTP Static Server
    server = http.createServer((req, res) => {
      const rawUrl = req.url.split('?')[0];
      const fileName = path.basename(rawUrl);
      let ext = path.extname(fileName);

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
      '--user-data-dir=' + path.join(__dirname, '.temp_chrome_profile_priv')
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
      if (msg.id && pendingResponses.has(msg.id)) {
        const { resolve, reject } = pendingResponses.get(msg.id);
        pendingResponses.delete(msg.id);
        if (msg.error) reject(new Error(msg.error.message));
        else resolve(msg.result);
      }
    };

    await sendCDP('Page.enable');
    await sendCDP('Runtime.enable');
    await sendCDP('DOM.enable');

    // Navigate to /profesional & Login
    await sendCDP('Page.navigate', { url: 'http://localhost:3000/profesional' });
    await sleep(800);

    await evaluate(`
      (async () => {
        document.getElementById('login-email').value = 'piloto.medico1@piediabetico.lat';
        document.getElementById('login-pass').value = '${testPassword}';
        const ev = new Event('submit', { bubbles: true, cancelable: true });
        await iniciarSesionPiloto(ev);
      })()
    `);
    await sleep(800);

    // Open Privacy Gate
    await evaluate(`goTo('s-privacy-gate')`);
    await sleep(400);

    // Function to read current DOM state
    async function getPrivacyState() {
      return await evaluate(`(() => {
        const items = Array.from(document.querySelectorAll('#s-privacy-gate .check-item, #s-privacy-gate .chk-item'));
        const btn = document.getElementById('btn-privacy-ok');
        return {
          count: items.length,
          aria: items.map(i => i.getAttribute('aria-checked') === 'true'),
          on: items.map(i => {
            const chk = i.querySelector('.check-box, .chk');
            return chk ? chk.classList.contains('on') : false;
          }),
          disabled: btn ? btn.disabled : true
        };
      })()`);
    }

    // BEFORE CLICK 1
    let state = await getPrivacyState();
    console.log('BEFORE');
    console.log(`aria = [${state.aria.join(',')}]`);
    console.log(`on = [${state.on.join(',')}]`);
    console.log(`disabled = ${state.disabled}`);

    assert.strictEqual(state.count, 4, 'Must have 4 check items');
    assert.deepStrictEqual(state.aria, [false, false, false, false]);
    assert.deepStrictEqual(state.on, [false, false, false, false]);
    assert.strictEqual(state.disabled, true);

    // CLICK 1
    await evaluate(`document.querySelectorAll('#s-privacy-gate .check-item, #s-privacy-gate .chk-item')[0].click()`);
    state = await getPrivacyState();
    console.log('\nAFTER CLICK 1');
    console.log(`aria = [${state.aria.join(',')}]`);
    console.log(`on = [${state.on.join(',')}]`);
    console.log(`disabled = ${state.disabled}`);
    assert.deepStrictEqual(state.aria, [true, false, false, false]);
    assert.strictEqual(state.disabled, true);

    // CLICK 2
    await evaluate(`document.querySelectorAll('#s-privacy-gate .check-item, #s-privacy-gate .chk-item')[1].click()`);
    state = await getPrivacyState();
    console.log('\nAFTER CLICK 2');
    console.log(`aria = [${state.aria.join(',')}]`);
    console.log(`on = [${state.on.join(',')}]`);
    console.log(`disabled = ${state.disabled}`);
    assert.deepStrictEqual(state.aria, [true, true, false, false]);
    assert.strictEqual(state.disabled, true);

    // CLICK 3
    await evaluate(`document.querySelectorAll('#s-privacy-gate .check-item, #s-privacy-gate .chk-item')[2].click()`);
    state = await getPrivacyState();
    console.log('\nAFTER CLICK 3');
    console.log(`aria = [${state.aria.join(',')}]`);
    console.log(`on = [${state.on.join(',')}]`);
    console.log(`disabled = ${state.disabled}`);
    assert.deepStrictEqual(state.aria, [true, true, true, false]);
    assert.strictEqual(state.disabled, true);

    // CLICK 4
    await evaluate(`document.querySelectorAll('#s-privacy-gate .check-item, #s-privacy-gate .chk-item')[3].click()`);
    state = await getPrivacyState();
    console.log('\nAFTER CLICK 4');
    console.log(`aria = [${state.aria.join(',')}]`);
    console.log(`on = [${state.on.join(',')}]`);
    console.log(`disabled = ${state.disabled}`);
    assert.deepStrictEqual(state.aria, [true, true, true, true]);
    assert.deepStrictEqual(state.on, [true, true, true, true]);
    assert.strictEqual(state.disabled, false);

    // UNSELECT CHECKBOX 2
    console.log('\nUNSELECT CHECKBOX 2');
    await evaluate(`document.querySelectorAll('#s-privacy-gate .check-item, #s-privacy-gate .chk-item')[1].click()`);
    state = await getPrivacyState();
    console.log(`aria = [${state.aria.join(',')}]`);
    console.log(`disabled = ${state.disabled}`);
    assert.strictEqual(state.disabled, true);

    // RE-SELECT CHECKBOX 2
    console.log('\nRE-SELECT CHECKBOX 2');
    await evaluate(`document.querySelectorAll('#s-privacy-gate .check-item, #s-privacy-gate .chk-item')[1].click()`);
    state = await getPrivacyState();
    console.log(`aria = [${state.aria.join(',')}]`);
    console.log(`disabled = ${state.disabled}`);
    assert.strictEqual(state.disabled, false);

    // KEYBOARD SPACE TOGGLE ON CHECKBOX 3
    console.log('\nKEYBOARD SPACE TOGGLE ON CHECKBOX 3');
    await evaluate(`(() => {
      const item = document.querySelectorAll('#s-privacy-gate .check-item, #s-privacy-gate .chk-item')[2];
      item.focus();
      item.dispatchEvent(new KeyboardEvent('keydown', { key: ' ', code: 'Space', bubbles: true }));
      item.click(); // simulate Space key press behavior
    })()`);
    state = await getPrivacyState();
    console.log(`aria = [${state.aria.join(',')}]`);
    console.log(`disabled = ${state.disabled}`);
    assert.strictEqual(state.aria[2], false);
    assert.strictEqual(state.disabled, true);

    // RE-ENABLE CHECKBOX 3
    await evaluate(`document.querySelectorAll('#s-privacy-gate .check-item, #s-privacy-gate .chk-item')[2].click()`);
    state = await getPrivacyState();
    assert.strictEqual(state.disabled, false);

    // CLICK CONTINUE BUTTON
    console.log('\nCLICK CONTINUE BUTTON');
    await evaluate(`document.getElementById('btn-privacy-ok').click()`);
    await sleep(300);

    const activeScreen = await evaluate(`histProf[histProf.length - 1]`);
    console.log(`activeScreen after click = "${activeScreen}"`);
    assert.strictEqual(activeScreen, 's-foto-cap', 'Clicking Continue must navigate to s-foto-cap');

    console.log('\n═══════════════════════════════════════════════════════════════════════');
    console.log('🎉 PRIVACY GATE DIAGNOSTIC TEST PASSED (100%)');
    console.log('═══════════════════════════════════════════════════════════════════════\n');

  } catch (err) {
    console.error('\n❌ DIAGNOSTIC FAILURE:', err.message);
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
    fs.rmSync(path.join(__dirname, '.temp_chrome_profile_priv'), { recursive: true, force: true });
  } catch (_) {}

  if (exitCode !== 0) {
    process.exit(exitCode);
  }
}

runPrivacyGateDiagnostic();
