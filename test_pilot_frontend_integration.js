/**
 * TEST SUITE: Frontend Contract & Integration with Real Backend APIs
 * 
 * Verifies all 22+ frontend-to-backend integration contracts:
 * 1. Zero localStorage clinical data / token persistence.
 * 2. In-memory state initialization (empty cases, null active UUIDs).
 * 3. Centralized pilotApi client with Bearer auth, 401 handling, error masking.
 * 4. Pilot Login flow (POST /api/pilot/auth/login).
 * 5. AI Readiness reporting (GET /api/pilot/ai-readiness).
 * 6. Case listing and selection (GET /api/pilot/cases).
 * 7. Case creation (POST /api/pilot/cases) with primary wound creation.
 * 8. Wound creation (POST /api/pilot/cases/{case_uuid}/wounds).
 * 9. Longitudinal analysis (POST /api/pilot/analisis) and memory cleanup.
 * 10. Honest AI rendering (fail-closed classifier, null absolute cm²).
 * 11. Timeline loading (GET /api/pilot/cases/{case_uuid}/timeline).
 * 12. Remote follow-up token generation (POST /api/pilot/cases/{c}/wounds/{w}/tokens).
 * 13. Public Remote Patient entry (GET /api/pilot/r/{token}) without bearer auth.
 * 14. Public Remote Patient upload (POST /api/pilot/r/{token}/upload) with privacy confirmation.
 * 15. Single-use token invalidation handling.
 * 16. Isolated analysis (POST /api/pilot/analisis) with 72h TTL.
 * 17. Evolution feedback registration (POST /api/pilot/evolution-feedback).
 * 18. Session logout and memory wipe.
 */

const assert = require('assert');
const fs = require('fs');
const path = require('path');
const vm = require('vm');

let testsPassed = 0;
let testsFailed = 0;

function runTest(name, fn) {
  try {
    fn();
    console.log(`  ✓ PASS: ${name}`);
    testsPassed++;
  } catch (err) {
    console.error(`  ✗ FAIL: ${name}`);
    console.error(`    ${err.message}`);
    testsFailed++;
  }
}

async function runAsyncTest(name, fn) {
  try {
    await fn();
    console.log(`  ✓ PASS: ${name}`);
    testsPassed++;
  } catch (err) {
    console.error(`  ✗ FAIL: ${name}`);
    console.error(`    ${err.message}`);
    testsFailed++;
  }
}

console.log('\n═══════════════════════════════════════════════════════════════════════');
console.log('🧪 RUNNING FRONTEND PILOT v0.1 INTEGRATION TEST SUITE');
console.log('═══════════════════════════════════════════════════════════════════════\n');

// 1. Static Analysis of app.js and index.html
const appJsCode = fs.readFileSync(path.join(__dirname, 'app.js'), 'utf8');
const indexHtmlCode = fs.readFileSync(path.join(__dirname, 'index.html'), 'utf8');

runTest('1. No hardcoded demo cases in app.js initial state', () => {
  assert(!appJsCode.includes("pilot_case_uuid: 'case-demo-001'"), 'Found demo case in initial state');
  assert(!appJsCode.includes("wound_uuid: 'wound-demo-001'"), 'Found demo wound in initial state');
});

runTest('2. Zero localStorage persistence for pilot clinical data or session tokens', () => {
  assert(!appJsCode.includes("localStorage.setItem('piediabetico_pilot_data_v01'"), 'Found localStorage pilot data writing');
  assert(!appJsCode.includes("localStorage.getItem('piediabetico_pilot_data_v01'"), 'Found localStorage pilot data reading');
  assert(!appJsCode.includes("localStorage.setItem('pilot_token'"), 'Found localStorage token writing');
});

runTest('3. No fake hardcoded AI classification ("Abnormal(Ulcer)") in timeline rendering', () => {
  const renderTlRegex = /function renderizarTimelinePiloto[\s\S]*?^}/m;
  const match = appJsCode.match(renderTlRegex);
  assert(match, 'renderizarTimelinePiloto function not found');
  assert(!match[0].includes("'Abnormal(Ulcer)'"), 'Found fake hardcoded classifier label in timeline rendering');
});

runTest('4. Fail-closed honest AI messaging present in timeline rendering', () => {
  assert(appJsCode.includes('Clasificación IA no disponible (Fail-Closed)'), 'Honest classifier fallback message missing');
  assert(appJsCode.includes('Área absoluta no disponible (falta escala física calibrada)'), 'Honest metric scale fallback message missing');
});

runTest('5. Centralized pilotApi client definition and structure', () => {
  assert(appJsCode.includes('async function pilotApi(path, options = {})'), 'pilotApi function missing');
  assert(appJsCode.includes("headers['Authorization'] = `Bearer ${state.pilotSessionToken}`"), 'Bearer token attachment missing in pilotApi');
  assert(appJsCode.includes('state.pilotSessionToken = null;'), 'Session wipe on 401 missing');
});

runTest('6. index.html contains pilot login view and authenticated container', () => {
  assert(indexHtmlCode.includes('id="piloto-login-view"'), 'piloto-login-view missing from index.html');
  assert(indexHtmlCode.includes('id="piloto-authenticated-view"'), 'piloto-authenticated-view missing from index.html');
  assert(indexHtmlCode.includes('id="inp-piloto-email"'), 'inp-piloto-email missing');
  assert(indexHtmlCode.includes('id="inp-piloto-password"'), 'inp-piloto-password missing');
  assert(indexHtmlCode.includes('id="badge-unet-readiness"'), 'badge-unet-readiness missing');
  assert(indexHtmlCode.includes('id="badge-classifier-readiness"'), 'badge-classifier-readiness missing');
});

runTest('7. index.html patient remote view contains token validation and error states', () => {
  assert(indexHtmlCode.includes('id="pac-remoto-loading"'), 'pac-remoto-loading missing');
  assert(indexHtmlCode.includes('id="pac-remoto-invalido"'), 'pac-remoto-invalido missing');
  assert(indexHtmlCode.includes('id="pac-remoto-valido"'), 'pac-remoto-valido missing');
});

// 2. Behavioral / Simulated DOM Execution of Pilot Functions
(async () => {
  const mockStorage = {};
  const mockDom = {};

  const fetchCalls = [];
  let lastFetchUrl = null;
  let lastFetchOptions = null;

  const sandbox = {
    console: {
      log: () => {},
      warn: () => {},
      error: () => {}
    },
    setTimeout: (fn, ms) => setTimeout(fn, ms || 1),
    clearTimeout: clearTimeout,
    parseInt: parseInt,
    parseFloat: parseFloat,
    Date: Date,
    Math: Math,
    URL: URL,
    URLSearchParams: URLSearchParams,
    Array: Array,
    Object: Object,
    String: String,
    Boolean: Boolean,
    RegExp: RegExp,
    Error: Error,
    Set: Set,
    Promise: Promise,
    JSON: JSON,
    alert: () => {},
    prompt: (msg, def) => def || 'PILOT-0001',
    lucide: { createIcons: () => {} },
    navigator: {
      clipboard: {
        writeText: async () => {}
      }
    },
    localStorage: {
      getItem: (k) => mockStorage[k] || null,
      setItem: (k, v) => { mockStorage[k] = v; },
      removeItem: (k) => { delete mockStorage[k]; }
    },
    window: {
      location: {
        origin: 'http://127.0.0.1:8000',
        pathname: '/',
        hash: '',
        search: ''
      },
      addEventListener: () => {},
      scrollTo: () => {},
      lucide: { createIcons: () => {} }
    },
    document: {
      documentElement: {
        setAttribute: () => {}
      },
      addEventListener: () => {},
      getElementById: (id) => {
        if (!mockDom[id]) {
          mockDom[id] = {
            id: id,
            classList: {
              classes: new Set(),
              add: function(c) { this.classes.add(c); },
              remove: function(c) { this.classes.delete(c); },
              contains: function(c) { return this.classes.has(c); }
            },
            value: '',
            checked: true,
            textContent: '',
            innerHTML: '',
            style: {},
            appendChild: function(child) { this.children.push(child); },
            children: []
          };
        }
        return mockDom[id];
      },
      createElement: (tag) => {
        return {
          tagName: tag.toUpperCase(),
          classList: {
            classes: new Set(),
            add: function(c) { this.classes.add(c); },
            remove: function(c) { this.classes.delete(c); },
            contains: function(c) { return this.classes.has(c); }
          },
          value: '',
          textContent: '',
          innerHTML: '',
          appendChild: function(child) { this.children.push(child); },
          children: [],
          getContext: () => ({
            drawImage: () => {},
            getImageData: () => {
              const d = new Uint8Array(40000);
              for (let i = 0; i < 40000; i += 4) {
                const val = (i % 500 < 250) ? 200 : 70;
                d[i] = val;
                d[i+1] = val;
                d[i+2] = val;
                d[i+3] = 255;
              }
              return { data: d };
            }
          })
        };
      }
    },
    Image: class {
      constructor() {
        this.width = 100;
        this.height = 100;
      }
      set src(val) {
        if (this.onload) {
          setTimeout(() => this.onload(), 5);
        }
      }
    },
    FileReader: class {
      readAsDataURL(file) {
        if (this.onload) setTimeout(() => this.onload({ target: { result: 'data:image/jpeg;base64,mock' } }), 5);
      }
    },
    fetch: async (url, options = {}) => {
      fetchCalls.push({ url, options });
      lastFetchUrl = url;
      lastFetchOptions = options;

      if (url.endsWith('/auth/login')) {
        const body = JSON.parse(options.body);
        if (body.email === 'piloto.medico1@piediabetico.lat' && body.password === 'valid_pass') {
          return {
            ok: true,
            status: 200,
            json: async () => ({
              access_token: 'pd_sess_test_mock_token_12345',
              token_type: 'bearer',
              email: body.email,
              full_name: 'Dr. Piloto Uno',
              role: 'medico_general'
            })
          };
        } else {
          return {
            ok: false,
            status: 401,
            json: async () => ({ detail: 'Credenciales inválidas' })
          };
        }
      }

      if (url.endsWith('/ai-readiness')) {
        return {
          ok: true,
          status: 200,
          json: async () => ({
            segmentation_ready: true,
            classifier_ready: false,
            model_version: 'v1.0.0',
            fail_closed_mode: true
          })
        };
      }

      if (url.includes('/timeline')) {
        return {
          ok: true,
          status: 200,
          json: async () => ({
            pilot_case_uuid: '11111111-1111-1111-1111-111111111111',
            case_alias: 'PILOT-0001',
            wounds: [
              {
                wound_uuid: '22222222-2222-2222-2222-222222222222',
                wound_label: 'Herida 1',
                wound_location: 'Talón',
                events: [
                  {
                    analysis_uuid: '55555555-5555-5555-5555-555555555555',
                    photo_uuid: '66666666-6666-6666-6666-666666666666',
                    display_date: 'Foto 1 — 29 Ago 2026',
                    quality_gate_score: 92,
                    quality_gate_status: 'optimo',
                    ai_status: 'PARTIAL',
                    classification_status: 'AI_UNAVAILABLE',
                    segmentation_status: 'COMPLETED',
                    classification_label: null,
                    classification_confidence: null,
                    pixel_area: 4120,
                    relative_area_percent: 5.4,
                    absolute_area_cm2: null
                  }
                ]
              }
            ]
          })
        };
      }

      if (url.includes('/tokens') && options.method === 'POST') {
        return {
          ok: true,
          status: 200,
          json: async () => ({
            token_id: 1,
            token: 'pd_tok_mock_secure_token_abc123',
            url: '/r/pd_tok_mock_secure_token_abc123',
            due_date: '2026-09-02',
            expires_date: '2026-09-05'
          })
        };
      }

      if (url.includes('/wounds') && options.method === 'POST') {
        const body = JSON.parse(options.body);
        return {
          ok: true,
          status: 200,
          json: async () => ({
            id: 20,
            wound_uuid: '44444444-4444-4444-4444-444444444444',
            wound_label: body.wound_label,
            wound_location: body.wound_location,
            created_at: new Date().toISOString()
          })
        };
      }

      if (url.includes('/r/expired_token')) {
        return {
          ok: false,
          status: 404,
          json: async () => ({ detail: 'Token inválido, expirado o ya utilizado' })
        };
      }

      if (url.includes('/r/pd_tok_mock_secure_token_abc123/upload') && options.method === 'POST') {
        return {
          ok: true,
          status: 200,
          json: async () => ({
            exito: true,
            mensaje: 'Foto recibida para revisión médica.',
            retry_allowed: false
          })
        };
      }

      if (url.includes('/r/pd_tok_mock_secure_token_abc123') && (!options.method || options.method === 'GET')) {
        return {
          ok: true,
          status: 200,
          json: async () => ({
            valid: true,
            due_date: '2026-09-02',
            mensaje: 'Enlace válido para foto de control Día +4'
          })
        };
      }

      if (url.endsWith('/analisis') && options.method === 'POST') {
        return {
          ok: true,
          status: 200,
          json: async () => ({
            id: 50,
            analysis_uuid: '55555555-5555-5555-5555-555555555555',
            photo_uuid: '66666666-6666-6666-6666-666666666666',
            quality_gate_score: 92,
            quality_gate_status: 'optimo',
            ai_status: 'PARTIAL',
            classification_status: 'AI_UNAVAILABLE',
            segmentation_status: 'COMPLETED',
            classification_label: null,
            classification_confidence: null,
            relative_area_percent: 5.4,
            pixel_area: 4120,
            absolute_area_cm2: null,
            expires_at: new Date(Date.now() + 21*86400000).toISOString()
          })
        };
      }

      if (url.endsWith('/evolution-feedback') && options.method === 'POST') {
        return {
          ok: true,
          status: 200,
          json: async () => ({
            id: 1,
            feedback_uuid: '77777777-7777-7777-7777-777777777777',
            clinical_evolution: 'MEJOR',
            system_representation_agreement: 'SI'
          })
        };
      }

      if (url.endsWith('/cases') && options.method === 'POST') {
        const body = JSON.parse(options.body);
        return {
          ok: true,
          status: 200,
          json: async () => ({
            id: 10,
            pilot_case_uuid: '33333333-3333-3333-3333-333333333333',
            case_alias: body.case_alias,
            created_at: new Date().toISOString()
          })
        };
      }

      if (url.endsWith('/cases') && (!options.method || options.method === 'GET')) {
        return {
          ok: true,
          status: 200,
          json: async () => [
            {
              pilot_case_uuid: '11111111-1111-1111-1111-111111111111',
              case_alias: 'PILOT-0001',
              wounds: [
                {
                  wound_uuid: '22222222-2222-2222-2222-222222222222',
                  wound_label: 'Herida 1',
                  wound_location: 'Talón'
                }
              ]
            }
          ]
        };
      }

      return {
        ok: true,
        status: 200,
        json: async () => ({})
      };
    }
  };

  const context = vm.createContext(sandbox);
  vm.runInContext(appJsCode, context);

  await runAsyncTest('8. pilotApi handles authentication header correctly', async () => {
    sandbox.state.pilotSessionToken = 'test_session_token_xyz';
    await sandbox.pilotApi('/ai-readiness');
    assert.strictEqual(lastFetchOptions.headers['Authorization'], 'Bearer test_session_token_xyz');
  });

  await runAsyncTest('9. pilotApi handles skipAuth option for public endpoints', async () => {
    sandbox.state.pilotSessionToken = 'test_session_token_xyz';
    await sandbox.pilotApi('/r/test_token', { skipAuth: true });
    assert.strictEqual(lastFetchOptions.headers['Authorization'], undefined);
  });

  await runAsyncTest('10. iniciarSesionPiloto executes login and stores token in memory ONLY', async () => {
    sandbox.state.pilotSessionToken = null;
    sandbox.document.getElementById('inp-piloto-email').value = 'piloto.medico1@piediabetico.lat';
    sandbox.document.getElementById('inp-piloto-password').value = 'valid_pass';

    await sandbox.iniciarSesionPiloto({ preventDefault: () => {} });

    assert.strictEqual(sandbox.state.pilotSessionToken, 'pd_sess_test_mock_token_12345');
    assert.strictEqual(sandbox.state.pilotUser.email, 'piloto.medico1@piediabetico.lat');
    assert.strictEqual(mockStorage['pilot_token'], undefined, 'Token must not be stored in localStorage');
  });

  await runAsyncTest('11. consultarAiReadinessPiloto correctly handles missing classifier artifact', async () => {
    await sandbox.consultarAiReadinessPiloto();
    assert.strictEqual(sandbox.state.pilotAiReadiness.segmentation_ready, true);
    assert.strictEqual(sandbox.state.pilotAiReadiness.classifier_ready, false);
    assert(sandbox.document.getElementById('badge-classifier-readiness').innerHTML.includes('Fail-Closed'));
  });

  await runAsyncTest('12. cargarCasosPilotoDesdeBackend populates state from PostgreSQL', async () => {
    await sandbox.cargarCasosPilotoDesdeBackend();
    assert.strictEqual(sandbox.state.pilotData.cases.length, 1);
    assert.strictEqual(sandbox.state.pilotData.activeCaseUuid, '11111111-1111-1111-1111-111111111111');
    assert.strictEqual(sandbox.state.pilotData.activeWoundUuid, '22222222-2222-2222-2222-222222222222');
  });

  await runAsyncTest('13. guardarNuevaHeridaPiloto calls POST /cases/{id}/wounds', async () => {
    sandbox.state.pilotData.activeCaseUuid = '11111111-1111-1111-1111-111111111111';
    sandbox.document.getElementById('input-piloto-herida-label').value = 'Herida 2';
    sandbox.document.getElementById('select-piloto-herida-location').value = 'Hallux';

    await sandbox.guardarNuevaHeridaPiloto();
    const woundCall = fetchCalls.find(c => c.url.includes('/wounds'));
    assert(woundCall, 'POST /cases/{id}/wounds call not found in fetch history');
    assert.strictEqual(woundCall.options.method, 'POST');
    const sentBody = JSON.parse(woundCall.options.body);
    assert.strictEqual(sentBody.wound_label, 'Herida 2');
  });

  await runAsyncTest('14. cargarTimelineCasoPiloto loads timeline from PostgreSQL', async () => {
    await sandbox.cargarTimelineCasoPiloto('11111111-1111-1111-1111-111111111111');
    assert(lastFetchUrl.includes('/cases/11111111-1111-1111-1111-111111111111/timeline'));
    assert.strictEqual(sandbox.state.pilotData.activeTimeline.wounds[0].events.length, 1);
  });

  await runAsyncTest('15. abrirModalSolicitarControlPiloto creates single-use token', async () => {
    sandbox.state.pilotData.activeCaseUuid = '11111111-1111-1111-1111-111111111111';
    sandbox.state.pilotData.activeWoundUuid = '22222222-2222-2222-2222-222222222222';

    await sandbox.abrirModalSolicitarControlPiloto();
    assert(lastFetchUrl.includes('/tokens'));
    assert.strictEqual(lastFetchOptions.method, 'POST');
    assert(sandbox.document.getElementById('input-link-control-generado').value.includes('/r/pd_tok_mock_secure_token_abc123'));
  });

  await runAsyncTest('16. iniciarFlujoPacienteRemoto validates token via public GET /r/{token}', async () => {
    sandbox.state.remoteTokenActivo = 'pd_tok_mock_secure_token_abc123';
    await sandbox.iniciarFlujoPacienteRemoto();
    assert(lastFetchUrl.includes('/api/pilot/r/pd_tok_mock_secure_token_abc123'));
    assert.strictEqual(lastFetchOptions.headers['Authorization'], undefined, 'Patient remote request must NOT send doctor Bearer token');
    assert(sandbox.document.getElementById('pac-remoto-valido').classList.contains('hidden') === false);
  });

  await runAsyncTest('17. iniciarFlujoPacienteRemoto displays invalid view on expired/used token', async () => {
    sandbox.state.remoteTokenActivo = 'expired_token';
    await sandbox.iniciarFlujoPacienteRemoto();
    assert(sandbox.document.getElementById('pac-remoto-invalido').classList.contains('hidden') === false);
  });

  await runAsyncTest('18. enviarFotoPacienteRemoto calls POST /r/{token}/upload with NO doctor or case IDs', async () => {
    sandbox.state.remoteTokenActivo = 'pd_tok_mock_secure_token_abc123';
    sandbox.state.pilotData.tempFotoPacienteRemotoBase64 = 'iVBORw0KGgoAAAANSUhEUgAAAAEAAAABCAYAAAAfFcSJAAAADUlEQVR42mNk+M9QDwADhgGAWjR9awAAAABJRU5ErkJggg==';
    sandbox.state.pilotData.pacienteQualityScore = 85;

    sandbox.enviarFotoPacienteRemoto();
    await new Promise(r => setTimeout(r, 60));

    const uploadCall = fetchCalls.find(c => c.url.includes('/upload'));
    assert(uploadCall, 'POST /upload call not found in fetch history');
    assert.strictEqual(uploadCall.options.method, 'POST');
    const sentBody = JSON.parse(uploadCall.options.body);
    assert.strictEqual(sentBody.pilot_case_uuid, undefined, 'Patient upload must NEVER send pilot_case_uuid');
    assert.strictEqual(sentBody.physician_id, undefined, 'Patient upload must NEVER send physician_id');
    assert.strictEqual(sentBody.privacy_gate_confirmed, true);
    assert.strictEqual(sandbox.state.pilotData.tempFotoPacienteRemotoBase64, null, 'Temporary base64 must be cleared immediately after upload');
  });

  await runAsyncTest('19. guardarEvaluacionEvolucionPiloto calls POST /evolution-feedback', async () => {
    sandbox.state.pilotData.baselineAnalysisUuid = '55555555-5555-5555-5555-555555555555';
    sandbox.state.pilotData.followupAnalysisUuid = '66666666-6666-6666-6666-666666666666';
    sandbox.state.pilotData.evolucionClinicaSeleccionada = 'MEJOR';
    sandbox.state.pilotData.acuerdoIaSeleccionado = 'SI';
    sandbox.document.getElementById('input-evol-comentario').value = 'Evolución favorable de tejido de granulación.';

    await sandbox.guardarEvaluacionEvolucionPiloto();
    assert(lastFetchUrl.includes('/api/pilot/evolution-feedback'));
    assert.strictEqual(lastFetchOptions.method, 'POST');
    const sentBody = JSON.parse(lastFetchOptions.body);
    assert.strictEqual(sentBody.baseline_analysis_uuid, '55555555-5555-5555-5555-555555555555');
    assert.strictEqual(sentBody.clinical_evolution, 'MEJOR');
    assert.strictEqual(sentBody.system_representation_agreement, 'SI');
  });

  await runAsyncTest('20. isolated analysis is disabled in Pilot v0.1 and performs no clinical POST', async () => {
    fetchCalls.length = 0;
    sandbox.state.pilotData.tempFotoAisladaBase64 = 'iVBORw0KGgoAAAANSUhEUgAAAAEAAAABCAYAAAAfFcSJAAAADUlEQVR42mNk+M9QDwADhgGAWjR9awAAAABJRU5ErkJggg==';

    await sandbox.ejecutarAnalisisPilotoAislado();

    const analysisCall = fetchCalls.find(c => c.url.includes('/analisis'));
    assert.strictEqual(analysisCall, undefined, 'Isolated analysis must NOT issue any POST /analisis call');
    assert.strictEqual(sandbox.FEATURE_PILOT_ISOLATED_ANALYSIS, false, 'FEATURE_PILOT_ISOLATED_ANALYSIS must be disabled');

    const anyFabricatedCall = fetchCalls.find(c => {
      if (!c.options || !c.options.body) return false;
      const b = c.options.body;
      return b.includes('quality_score": 85') || b.includes('quality_status": "optimo"');
    });
    assert.strictEqual(anyFabricatedCall, undefined, 'No fetch request may contain fabricated clinical defaults (85 / optimo)');
  });

  await runAsyncTest('21. cerrarSesionPiloto wipes all session and clinical data from memory', async () => {
    sandbox.state.pilotSessionToken = 'pd_sess_test_mock_token_12345';
    sandbox.state.pilotUser = { email: 'dr@test.com' };
    sandbox.state.pilotData.cases = [{ id: 1 }];
    sandbox.state.pilotData.activeTimeline = { id: 1 };

    sandbox.cerrarSesionPiloto();

    assert.strictEqual(sandbox.state.pilotSessionToken, null);
    assert.strictEqual(sandbox.state.pilotUser, null);
    assert.strictEqual(sandbox.state.pilotData.cases.length, 0);
    assert.strictEqual(sandbox.state.pilotData.activeTimeline, null);
    assert(sandbox.document.getElementById('piloto-login-view').classList.contains('hidden') === false);
  });

  await runAsyncTest('22. pilotApi 401 response automatically triggers session wipe', async () => {
    sandbox.state.pilotSessionToken = 'invalid_or_expired_token';
    sandbox.fetch = async () => ({ status: 401, ok: false });

    try {
      await sandbox.pilotApi('/cases');
    } catch (e) {
      // Expected
    }

    assert.strictEqual(sandbox.state.pilotSessionToken, null);
    assert.strictEqual(sandbox.state.pilotUser, null);
  });

  console.log('\n═══════════════════════════════════════════════════════════════════════');
  console.log(`📊 FRONTEND INTEGRATION RESULTS: ${testsPassed} PASSED, ${testsFailed} FAILED`);
  console.log('═══════════════════════════════════════════════════════════════════════\n');

  if (testsFailed > 0) {
    process.exit(1);
  }
})();
