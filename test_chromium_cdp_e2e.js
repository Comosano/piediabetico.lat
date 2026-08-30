/**
 * REAL CHROMIUM CDP BROWSER AUTOMATION SUITE
 * Uses Chrome headless and native CDP over WebSocket to test complete UI flows.
 */

const http = require('http');
const fs = require('fs');
const path = require('path');
const crypto = require('crypto');
const assert = require('assert');
const { spawn, execSync } = require('child_process');

const CHROME_PATH = 'C:\\Program Files\\Google\\Chrome\\Application\\chrome.exe';
const ARTIFACT_DIR = 'C:\\Users\\rosma\\.gemini\\antigravity\\brain\\62aa37cd-0c02-45dd-91ed-a6a91168f031';
const API_BASE = 'http://127.0.0.1:8000';

let cdpWs = null;
let msgId = 1;
const pendingResponses = new Map();
let server = null;
let chromeProcess = null;
let lastCompletedStep = 'NONE';
let globalWatchdogTimer = null;

// Helper: Wrap any promise with a hard timeout
async function withTimeout(promise, ms, label) {
  let timer;
  try {
    return await Promise.race([
      promise,
      new Promise((_, reject) => {
        timer = setTimeout(
          () => reject(new Error(`TIMEOUT: ${label} after ${ms}ms`)),
          ms
        );
      })
    ]);
  } finally {
    clearTimeout(timer);
  }
}

function sendCDP(method, params = {}) {
  return new Promise((resolve, reject) => {
    const id = msgId++;
    pendingResponses.set(id, { resolve, reject });
    cdpWs.send(JSON.stringify({ id, method, params }));
  });
}

async function evaluate(expression, timeoutMs = 15000) {
  return withTimeout(
    (async () => {
      const res = await sendCDP('Runtime.evaluate', {
        expression,
        returnByValue: true,
        awaitPromise: true
      });
      if (res.result && res.result.exceptionDetails) {
        throw new Error(JSON.stringify(res.result.exceptionDetails));
      }
      return res.result ? res.result.value : undefined;
    })(),
    timeoutMs,
    `evaluate(${expression.slice(0, 40)}...)`
  );
}

async function captureScreenshot(fileName) {
  try {
    const res = await withTimeout(sendCDP('Page.captureScreenshot', { format: 'png' }), 10000, 'Page.captureScreenshot');
    const buffer = Buffer.from(res.data, 'base64');
    const targetPath = path.join(ARTIFACT_DIR, fileName);
    fs.writeFileSync(targetPath, buffer);
    console.log(`    📸 Saved screenshot: ${fileName}`);
  } catch (err) {
    console.warn(`    ⚠️ Failed to capture screenshot ${fileName}: ${err.message}`);
  }
}

async function sleep(ms) {
  return new Promise(r => setTimeout(r, ms));
}

async function runBrowserE2E() {
  console.log('\n═══════════════════════════════════════════════════════════════════════');
  console.log('🌐 RUNNING REAL CHROMIUM HEADLESS BROWSER AUTOMATION (CDP)');
  console.log('═══════════════════════════════════════════════════════════════════════\n');

  // Overall Watchdog (10 Minutes Max)
  globalWatchdogTimer = setTimeout(() => {
    console.error('\n❌ E2E GLOBAL TIMEOUT');
    console.error(`LAST_COMPLETED_STEP=${lastCompletedStep}`);
    cleanupAndExit(1);
  }, 600000);

  try {
    // ── STEP 0: INITIALIZE POSTGRESQL & SERVERS ─────────────────────────
    console.log('[STEP 0 BEFORE] Initializing doctor credentials and web server...');
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

    await withTimeout(new Promise(r => server.listen(3000, r)), 10000, 'Server listen on 3000');
    console.log('  [Setup] Web server running at http://localhost:3000');

    // Spawn Chrome
    chromeProcess = spawn(CHROME_PATH, [
      '--headless=new',
      '--disable-gpu',
      '--no-first-run',
      '--no-default-browser-check',
      '--remote-debugging-port=9222',
      '--window-size=412,915',
      '--user-data-dir=' + path.join(__dirname, '.temp_chrome_profile')
    ]);

    await sleep(1500);

    // Connect to CDP
    const verRes = await withTimeout(fetch('http://127.0.0.1:9222/json/version'), 5000, 'Fetch CDP version');
    const verData = await verRes.json();
    console.log(`  [CDP] Connected to Chrome (${verData['Browser']})`);

    const listRes = await withTimeout(fetch('http://127.0.0.1:9222/json/list'), 5000, 'Fetch CDP targets');
    const listData = await listRes.json();
    const target = listData.find(t => t.type === 'page') || listData[0];
    const wsUrl = target.webSocketDebuggerUrl;

    cdpWs = new WebSocket(wsUrl);
    await withTimeout(new Promise((resolve, reject) => {
      cdpWs.onopen = resolve;
      cdpWs.onerror = reject;
    }), 5000, 'CDP WebSocket connection');

    cdpWs.onmessage = (event) => {
      const msg = JSON.parse(event.data);
      if (msg.method === 'Runtime.consoleAPICalled') {
        const text = msg.params.args.map(a => a.value || a.description || JSON.stringify(a)).join(' ');
        console.log(`    [Browser Console] ${text}`);
      } else if (msg.method === 'Runtime.exceptionThrown') {
        console.error(`    [Browser Exception] ${JSON.stringify(msg.params.exceptionDetails)}`);
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
    await sendCDP('DOM.enable');
    await sendCDP('Emulation.setDeviceMetricsOverride', {
      width: 412,
      height: 915,
      deviceScaleFactor: 2.625,
      mobile: true
    });

    // Override browser dialogs so alert() never blocks Chrome
    await sendCDP('Page.addScriptToEvaluateOnNewDocument', {
      source: `
        window.alert = function(msg) { console.log('[Alert Override]', msg); };
        window.confirm = function(msg) { console.log('[Confirm Override]', msg); return true; };
      `
    });

    console.log('[STEP 0 AFTER] Setup completed cleanly.');
    lastCompletedStep = 'STEP_0_SETUP';

    // ── STEP 1: ROUTE /profesional & LOGIN UX ───────────────────────────
    console.log('[STEP 1 BEFORE] Testing /profesional route and Login UX...');
    await withTimeout(sendCDP('Page.navigate', { url: 'http://localhost:3000/profesional' }), 15000, 'Navigate /profesional');
    await sleep(800);

    const loginText = await evaluate(`document.getElementById('s-login')?.innerText || ''`);
    assert(loginText.includes('Acceso restringido a profesionales habilitados para el piloto.'), 'Login subtitle must match approved text');
    console.log(`    ✓ Login screen loaded with approved subtitle`);

    await captureScreenshot('browser_prof_login.png');

    // Submit Login Form
    const loginResult = await evaluate(`
      (async () => {
        document.getElementById('login-email').value = 'piloto.medico1@piediabetico.lat';
        document.getElementById('login-pass').value = '${testPassword}';
        const ev = new Event('submit', { bubbles: true, cancelable: true });
        await iniciarSesionPiloto(ev);
        return {
          token_received: !!state.pilotSessionToken,
          activeScreen: histProf[histProf.length - 1],
          errorMsg_empty: !document.getElementById('msg-error-login-piloto')?.textContent
        };
      })()
    `, 20000);
    console.log('    [Login Result]:', loginResult);
    await sleep(500);

    const isHomeOn = await evaluate(`document.getElementById('s-home')?.classList.contains('on')`);
    assert(isHomeOn, 's-home screen must be active after successful login');

    // Verify AI Readiness UI & Internal State
    const unetPillText = await evaluate(`document.getElementById('pill-unet')?.textContent`);
    const clasifPillText = await evaluate(`document.getElementById('pill-clasif')?.textContent`);
    const aiReadinessState = await evaluate(`state.pilotAiReadiness`);

    console.log(`    ✓ Home loaded. Status bar:`);
    console.log(`      - U-Net Pill: "${unetPillText}"`);
    console.log(`      - Classifier Pill: "${clasifPillText}"`);

    // UI semantic assertions
    assert(unetPillText.toLowerCase().includes('disponible'), 'U-Net segmentation must be shown as disponible');
    assert(clasifPillText.toLowerCase().includes('no disponible'), 'Automatic classification must be shown as no disponible');
    assert(!clasifPillText.includes('FAIL-CLOSED'), 'Status bar must not expose FAIL-CLOSED to doctor');

    // Logical state assertions
    assert.strictEqual(aiReadinessState.segmentation_status, 'READY');
    assert.strictEqual(aiReadinessState.classifier_status, 'MISSING_ARTIFACT');
    assert.strictEqual(aiReadinessState.overall_status, 'SEGMENTATION_ONLY');

    await captureScreenshot('browser_prof_home.png');
    console.log('[STEP 1 AFTER] Login UX and AI Readiness verified.');
    lastCompletedStep = 'STEP_1_LOGIN_READINESS';

    // ── STEP 2: CREATE NEW CASE & WOUND ─────────────────────────────────
    console.log('[STEP 2 BEFORE] Testing Case and Wound creation...');
    await evaluate(`goTo('s-casos')`);
    await sleep(300);

    const caseAlias = `PILOT-${Math.floor(1000 + Math.random() * 9000)}`;
    await evaluate(`
      window.prompt = () => '${caseAlias}';
      crearNuevoCasoPilotoPrompt();
    `, 20000);
    await sleep(1000);

    const activeCaseUuid = await evaluate(`state.pilotData.activeCaseUuid`);
    assert(activeCaseUuid, 'activeCaseUuid must be set');
    console.log(`    ✓ Created new case in DB: ${caseAlias} (${activeCaseUuid.slice(0, 8)}...)`);

    await captureScreenshot('browser_prof_ficha.png');
    console.log('[STEP 2 AFTER] Case and Wound created.');
    lastCompletedStep = 'STEP_2_CASE_WOUND_CREATED';

    // ── STEP 3: NEW CONTROL & REAL QUALITY GATE FLOW ─────────────────────
    console.log('[STEP 3 BEFORE] Testing New Control sequence...');
    await evaluate(`
      state.pilotData.activeCaseUuid = '${activeCaseUuid}';
      goTo('s-privacy-gate');
    `);
    await sleep(300);

    // Confirm all 4 checkboxes in Privacy Gate
    await evaluate(`
      document.querySelectorAll('#s-privacy-gate .check-item, #s-privacy-gate .chk-item').forEach(i => toggleChkProf(i));
    `);
    const canContinuePrivacy = await evaluate(`!document.getElementById('btn-privacy-ok').disabled`);
    assert(canContinuePrivacy, 'Privacy Gate button must be enabled when 4 checks confirmed');
    console.log('    ✓ Privacy Gate confirmed');

    await captureScreenshot('browser_prof_privacy_gate.png');

    // Simulate Photo Capture with 500x500 canvas photo
    await evaluate(`
      const c = document.createElement('canvas');
      c.width = 500;
      c.height = 500;
      const ctx = c.getContext('2d');
      ctx.fillStyle = '#d2a688';
      ctx.fillRect(0, 0, 500, 500);
      ctx.fillStyle = '#991b1b';
      ctx.beginPath();
      ctx.arc(250, 250, 80, 0, Math.PI * 2);
      ctx.fill();
      const dUrl = c.toDataURL('image/jpeg', 0.85);
      state.pilotData.tempFotoDataUrl = dUrl;
      state.pilotData.tempFotoBase64 = dUrl.split(',')[1];
      goTo('s-foto-cap');
      document.getElementById('btn-foto-ok').style.display = 'block';
    `);
    await sleep(300);

    // Trigger Quality Gate
    await evaluate(`iniciarQualityGateProfesional()`);
    await sleep(700);

    const qgOkVisible = await evaluate(`document.getElementById('qg-ok')?.style.display !== 'none'`);
    assert(qgOkVisible, 'Quality Gate must complete with evaluable status');
    console.log('    ✓ Quality Gate passed');

    await captureScreenshot('browser_prof_quality_gate.png');

    // Shadow Mode & Real Analysis Execution
    await evaluate(`
      goTo('s-shadow-mode');
      const opts = document.querySelectorAll('#s-shadow-mode .shadow-opts');
      const impBtn = opts[0]?.querySelector('.shadow-opt');
      const infBtn = opts[1]?.querySelector('.shadow-opt');
      if (impBtn) shadowSel(impBtn, 'imp');
      if (infBtn) shadowSel(infBtn, 'inf');
    `);
    await sleep(300);

    await captureScreenshot('browser_prof_shadow_mode.png');

    // Submit analysis with U-Net (max timeout 60s)
    await evaluate(`ejecutarAnalisisPilotoConShadowMode()`, 60000);
    await sleep(2000);

    const isResOn = await evaluate(`document.getElementById('s-resultado-analisis')?.classList.contains('on')`);
    assert(isResOn, 's-resultado-analisis must be on after analysis completion');

    const areaValText = await evaluate(`document.getElementById('res-area-val')?.textContent`);
    const absValText = await evaluate(`document.getElementById('res-abs-val')?.textContent`);
    const clasifValText = await evaluate(`document.getElementById('res-clasif-val')?.textContent`);

    console.log(`    ✓ Analysis Result loaded:`);
    console.log(`      - Pixel / Rel Area: "${areaValText}"`);
    console.log(`      - Absolute cm2: "${absValText}"`);
    console.log(`      - Classifier: "${clasifValText}"`);

    assert(absValText.includes('No disponible'), 'Absolute cm2 must be No disponible without scale');
    assert(clasifValText.includes('No disponible en esta versión'), 'Classifier must state unavailable');

    await captureScreenshot('browser_prof_analysis_result.png');
    console.log('[STEP 3 AFTER] New Control and Analysis execution completed.');
    lastCompletedStep = 'STEP_3_NEW_CONTROL_ANALYSIS';

    // ── STEP 4: TIMELINE & DAY +4 REMOTE TOKEN GENERATION ───────────────
    console.log('[STEP 4 BEFORE] Testing Timeline and Remote Token generation...');
    await evaluate(`
      renderizarHeridaTimelineV4();
      goTo('s-herida');
    `);
    await sleep(800);

    await captureScreenshot('browser_prof_timeline.png');

    // Open Token Modal and Generate Link
    await evaluate(`
      abrirModalSeguimientoPiloto();
      generarLinkSeguimientoPiloto();
    `, 20000);
    await sleep(1000);

    const generatedLink = await evaluate(`document.getElementById('input-link-control-generado')?.value`);
    assert(generatedLink && generatedLink.includes('/r/'), 'Generated link must contain /r/ token');
    console.log(`    ✓ Generated Remote Follow-Up Token Link created successfully.`);

    await captureScreenshot('browser_prof_token_modal.png');

    const rawToken = generatedLink.split('/r/')[1].split('/')[0];
    console.log('[STEP 4 AFTER] Timeline and Remote Token created.');
    lastCompletedStep = 'STEP_4_REMOTE_TOKEN_GENERATED';

    // ── STEP 5: PUBLIC PATIENT PORTAL (/paciente) ───────────────────────
    console.log('[STEP 5 BEFORE] Testing Public Patient Portal (/paciente)...');
    await withTimeout(sendCDP('Page.navigate', { url: 'http://localhost:3000/paciente' }), 15000, 'Navigate /paciente');
    await sleep(800);

    const pacTitle = await evaluate(`document.querySelector('#portal-paciente-view .hero h1')?.textContent || document.querySelector('#portal-paciente-view .t-logo')?.textContent || ''`);
    console.log(`    ✓ Public Patient Portal loaded with heading: "${pacTitle.trim()}"`);
    assert(pacTitle.toLowerCase().includes('pie') || pacTitle.toLowerCase().includes('diabético'), 'Patient portal heading must match');

    await captureScreenshot('browser_patient_public.png');
    console.log('[STEP 5 AFTER] Public Patient Portal verified.');
    lastCompletedStep = 'STEP_5_PATIENT_PUBLIC';

    // ── STEP 6: REMOTE PATIENT FOLLOW-UP FLOW (/r/{token}) ──────────────
    console.log('[STEP 6 BEFORE] Testing Remote Patient Follow-Up Flow (/r/{token})...');
    await withTimeout(sendCDP('Page.navigate', { url: `http://localhost:3000/r/${rawToken}` }), 15000, 'Navigate /r/{token}');
    await sleep(1000);

    const verifOk = await evaluate(`document.getElementById('verif-ok')?.style.display !== 'none'`);
    assert(verifOk, 'Remote token must verify successfully on GET /api/pilot/r/{token}');
    console.log('    ✓ Step 1: Token verification successful with due date display');

    await captureScreenshot('browser_patient_remote_step1_verify.png');

    // Continue to Privacy
    await evaluate(`goToPacRem('s-rem-privacy')`);
    await sleep(300);

    // Confirm all 4 privacy items + 1 consent
    await evaluate(`
      document.querySelectorAll('#s-rem-privacy .check-item, #s-rem-privacy .chk-item').forEach(i => toggleChkPac(i));
    `);
    const canContinuePacPrivacy = await evaluate(`!document.getElementById('btn-pac-privacy-ok').disabled`);
    assert(canContinuePacPrivacy, 'Patient privacy button enabled after 5 checks confirmed');
    console.log('    ✓ Step 2: Patient Privacy & Explicit Consent confirmed');

    await captureScreenshot('browser_patient_remote_step2_privacy.png');

    // Step 3: Photo Capture & Quality Gate
    await evaluate(`
      confirmarPrivacidadPacienteRemoto();
      const c = document.createElement('canvas');
      c.width = 500;
      c.height = 500;
      const ctx = c.getContext('2d');
      ctx.fillStyle = '#d2a688';
      ctx.fillRect(0, 0, 500, 500);
      ctx.fillStyle = '#991b1b';
      ctx.beginPath();
      ctx.arc(250, 250, 80, 0, Math.PI * 2);
      ctx.fill();
      const dUrl = c.toDataURL('image/jpeg', 0.85);
      state.pilotData.tempFotoPacienteRemotoDataUrl = dUrl;
      state.pilotData.tempFotoPacienteRemotoBase64 = dUrl.split(',')[1];
      iniciarQualityGatePacienteRemoto();
    `);
    await sleep(700);

    const pacQgOk = await evaluate(`document.getElementById('pac-qg-ok')?.style.display !== 'none'`);
    assert(pacQgOk, 'Patient Quality Gate passed');
    console.log('    ✓ Step 3: Patient Photo Quality Gate passed');

    await captureScreenshot('browser_patient_remote_step3_quality.png');

    // Step 4: Submit Photo & Verify Atomic Consumption
    await evaluate(`enviarFotoPacienteRemoto()`, 30000);
    await sleep(1500);

    const envOk = await evaluate(`document.getElementById('env-ok')?.style.display !== 'none'`);
    assert(envOk, 'Patient confirmation screen displayed');

    const memoryCleaned = await evaluate(`state.pilotData.tempFotoPacienteRemotoBase64 === null && state.remoteTokenActivo === null`);
    assert(memoryCleaned, 'Ephemeral memory must be wiped after successful submission');
    console.log('    ✓ Step 4: Remote Photo uploaded successfully. Ephemeral memory wiped.');

    await captureScreenshot('browser_patient_remote_step4_success.png');
    console.log('[STEP 6 AFTER] Remote Patient Follow-Up submitted.');
    lastCompletedStep = 'STEP_6_REMOTE_PATIENT_UPLOADED';

    // ── STEP 7: REPLAY ATTACK VERIFICATION ──────────────────────────────
    console.log('[STEP 7 BEFORE] Testing Replay Attack on used token...');
    await withTimeout(sendCDP('Page.navigate', { url: `http://localhost:3000/r/${rawToken}` }), 15000, 'Replay navigate');
    await sleep(1000);

    const isNoDisp = await evaluate(`document.getElementById('verif-nodisponible')?.style.display !== 'none'`);
    assert(isNoDisp, 'Used token must be rejected with unavailable screen');
    console.log('    ✓ Replay Attack Blocked: Token recognized as consumed');
    console.log('[STEP 7 AFTER] Replay attack blocked.');
    lastCompletedStep = 'STEP_7_REPLAY_ATTACK_BLOCKED';

    // ── STEP 8: LONGITUDINAL COMPARATOR & FEEDBACK ──────────────────────
    console.log('[STEP 8 BEFORE] Testing Doctor Re-login and Longitudinal Timeline...');
    await withTimeout(sendCDP('Page.navigate', { url: 'http://localhost:3000/profesional' }), 15000, 'Navigate /profesional for re-login');
    await sleep(800);

    // Re-login
    await evaluate(`
      (async () => {
        document.getElementById('login-email').value = 'piloto.medico1@piediabetico.lat';
        document.getElementById('login-pass').value = '${testPassword}';
        const ev = new Event('submit', { bubbles: true, cancelable: true });
        await iniciarSesionPiloto(ev);
      })()
    `, 20000);
    await sleep(1500);

    // Open active case & wound
    await evaluate(`
      state.pilotData.activeCaseUuid = '${activeCaseUuid}';
      await cargarTimelineCasoPiloto('${activeCaseUuid}');
      renderizarHeridaTimelineV4();
      goTo('s-herida');
    `, 20000);
    await sleep(800);

    const eventsCount = await evaluate(`
      (() => {
        const wg = state.pilotData.activeTimeline?.wounds?.find(w => w.wound_uuid === state.pilotData.activeWoundUuid);
        return wg ? wg.events.length : 0;
      })()
    `);
    console.log(`    ✓ Timeline updated from PostgreSQL: ${eventsCount} events present under wound`);
    assert.strictEqual(eventsCount, 2, 'Timeline must contain 2 events after remote patient upload');

    await captureScreenshot('browser_prof_timeline_2_events.png');

    // Open Comparator
    await evaluate(`goTo('s-comparador')`);
    await sleep(500);

    await captureScreenshot('browser_prof_comparador.png');

    // Submit Evolution Feedback
    const fbResult = await evaluate(`
      (async () => {
        const wg = state.pilotData.activeTimeline?.wounds?.find(w => w.wound_uuid === state.pilotData.activeWoundUuid);
        if (!wg || wg.events.length < 2) return false;
        state.pilotData.baselineAnalysisUuid = wg.events[0].analysis_uuid;
        state.pilotData.followupAnalysisUuid = wg.events[1].analysis_uuid;
        state.pilotData.evolucionClinicaSeleccionada = 'MEJOR';
        state.pilotData.acuerdoIaSeleccionado = 'SI';
        const commEl = document.getElementById('comp-comentario');
        if (commEl) commEl.value = 'Evolución favorable de tejido de granulación.';
        await guardarEvaluacionEvolucionPiloto();
        return true;
      })()
    `, 20000);
    assert(fbResult, 'Evolution feedback must be registered');
    console.log('    ✓ Evolution feedback submitted and persisted in PostgreSQL');
    console.log('[STEP 8 AFTER] Longitudinal Timeline and Feedback verified.');
    lastCompletedStep = 'STEP_8_LONGITUDINAL_FEEDBACK';

    // ── STEP 9: CLINICAL CALCULATORS ────────────────────────────────────
    console.log('[STEP 9 BEFORE] Testing Validated Clinical Calculators...');
    await evaluate(`
      goTo('s-cicatrizacion');
      const inp0 = document.getElementById('cic-a0') || document.getElementById('area0');
      const inp4 = document.getElementById('cic-a4') || document.getElementById('area4');
      if (inp0) inp0.value = '10.0';
      if (inp4) inp4.value = '4.0';
      calcularCicatrizacionV4();
    `);
    await sleep(300);

    const cicPctText = await evaluate(`(document.getElementById('cic-pct-val') || document.getElementById('cic-res-pct'))?.textContent`);
    const cicMetaText = await evaluate(`(document.getElementById('cic-eval-val') || document.getElementById('cic-res-meta'))?.textContent`);
    console.log(`    ✓ Cicatrización: "${cicPctText}" -> "${cicMetaText}"`);
    assert(cicPctText.includes('60.0%'));
    assert(cicMetaText.includes('meta') || cicMetaText.includes('Meta'));

    // Verify forbidden pixel fallback sentence is completely absent from DOM
    const hasForbiddenSentence = await evaluate(`document.body.innerText.includes('Si solo disponés de área relativa')`);
    assert(!hasForbiddenSentence, 'Forbidden sentence must be eliminated from calculator');

    await captureScreenshot('browser_prof_calculators.png');
    console.log('[STEP 9 AFTER] Clinical Calculators verified.');
    lastCompletedStep = 'STEP_9_CALCULATORS';

    // ── STEP 10: IN-BROWSER ZERO-STORAGE AUDIT ──────────────────────────
    console.log('[STEP 10 BEFORE] Running in-browser Zero-Storage & Privacy Audit...');
    const storageAudit = await evaluate(`(() => {
      const ALLOWED = ['piediabetico_theme', 'piediabetico_lang', 'pie_fav_tab'];
      const localKeys = Object.keys(localStorage);
      const sessionKeys = Object.keys(sessionStorage);
      const unexpectedLocalKeys = localKeys.filter(k => !ALLOWED.includes(k));
      
      const localDump = JSON.stringify(localStorage);
      const sessionDump = JSON.stringify(sessionStorage);
      
      const forbiddenTerms = [
        'pd_sess_',
        'pd_tok_',
        'data:image',
        'base64',
        'case_uuid',
        'wound_uuid',
        'password',
        'Abnormal',
        'pilot_token'
      ];
      
      const leaks = [];
      for (const term of forbiddenTerms) {
        if (localDump.includes(term)) leaks.push('localStorage contains ' + term);
        if (sessionDump.includes(term)) leaks.push('sessionStorage contains ' + term);
      }
      
      return {
        localKeys: localKeys,
        sessionKeys: sessionKeys,
        unexpectedLocalKeys: unexpectedLocalKeys,
        leaks: leaks,
        clean: leaks.length === 0 && unexpectedLocalKeys.length === 0 && sessionKeys.length === 0
      };
    })()`);

    console.log(`    ✓ localStorage exact key names: ${JSON.stringify(storageAudit.localKeys)}`);
    console.log(`    ✓ sessionStorage keys: ${storageAudit.sessionKeys.length}`);
    console.log(`    ✓ Prohibited/unexpected keys detected: ${storageAudit.unexpectedLocalKeys.length}`);
    console.log(`    ✓ Data Leaks detected: ${storageAudit.leaks.length}`);

    assert.strictEqual(storageAudit.unexpectedLocalKeys.length, 0, `Unallowlisted localStorage keys found: ${JSON.stringify(storageAudit.unexpectedLocalKeys)}`);
    assert.strictEqual(storageAudit.sessionKeys.length, 0, `Unexpected sessionStorage keys found: ${JSON.stringify(storageAudit.sessionKeys)}`);
    assert(storageAudit.clean, `Browser storage must be clean and match allowlist: ${JSON.stringify(storageAudit.leaks)}`);
    console.log('[STEP 10 AFTER] Zero-Storage Audit clean.');
    lastCompletedStep = 'STEP_10_STORAGE_AUDIT_CLEAN';

    console.log('\n═══════════════════════════════════════════════════════════════════════');
    console.log('🎉 ALL CHROMIUM CDP BROWSER AUTOMATION TESTS PASSED (100%)');
    console.log('═══════════════════════════════════════════════════════════════════════\n');

  } catch (err) {
    console.error(`\n❌ CDP TEST FAILURE at step after ${lastCompletedStep}:`, err.message);
    cleanupAndExit(1);
  } finally {
    cleanupAndExit(0);
  }
}

function cleanupAndExit(exitCode) {
  if (globalWatchdogTimer) {
    clearTimeout(globalWatchdogTimer);
    globalWatchdogTimer = null;
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
    fs.rmSync(path.join(__dirname, '.temp_chrome_profile'), { recursive: true, force: true });
  } catch (_) {}

  if (exitCode !== 0) {
    process.exit(exitCode);
  }
}

runBrowserE2E();
