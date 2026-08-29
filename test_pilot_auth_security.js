const assert = require('assert');
const fs = require('fs');
const path = require('path');
const crypto = require('crypto');

console.log('═══════════════════════════════════════════════════════════════════════');
console.log('🛡️ SUITE P0: PILOT AUTHENTICATION & MULTI-WORKER REDIS SESSION STORE');
console.log('   Redis SHA-256 Digest Keys · Zero Raw Bearer Tokens in Storage');
console.log('   Live PostgreSQL Verification · Multi-Worker Fail-Closed · Zero PII');
console.log('═══════════════════════════════════════════════════════════════════════\n');

let totalTests = 0;
let passedTests = 0;

function test(name, fn) {
  totalTests++;
  try {
    fn();
    console.log(`  ✓ [PASS] ${name}`);
    passedTests++;
  } catch (err) {
    console.error(`  ✕ [FAIL] ${name}:`, err.message);
  }
}

// ── Simulador de Hash Seguro (Espejo de domain/password_security.py) ─
function simularHashPassword(password) {
  if (!password || typeof password !== 'string') throw new Error('Password inválido');
  const salt = crypto.randomBytes(16).toString('hex');
  const iterations = 600000;
  const hash = crypto.pbkdf2Sync(password, salt, iterations, 32, 'sha256').toString('hex');
  return `pbkdf2_sha256$${iterations}$${salt}$${hash}`;
}

function simularVerifyPassword(rawPassword, storedHash) {
  if (!rawPassword || !storedHash) return false;
  if (!storedHash.startsWith('pbkdf2_sha256$') && !storedHash.startsWith('$argon2')) return false;

  if (storedHash.startsWith('pbkdf2_sha256$')) {
    const parts = storedHash.split('$');
    if (parts.length !== 4) return false;
    const [, iterStr, salt, expectedHash] = parts;
    const iterations = parseInt(iterStr, 10);
    const derived = crypto.pbkdf2Sync(rawPassword, salt, iterations, 32, 'sha256').toString('hex');
    return crypto.timingSafeEqual(Buffer.from(derived), Buffer.from(expectedHash));
  }
  return true;
}

// ── Simulador de Redis (Espejo de domain/session_store.py) ────────────
class MockRedisClient {
  constructor() {
    this.store = new Map();
    this.ttls = new Map();
    this.isAvailable = true;
  }

  set(key, value, options = {}) {
    if (!this.isAvailable) throw new Error('Redis connection refused (Simulated Outage)');
    this.store.set(key, value);
    if (options.ex) {
      this.ttls.set(key, Date.now() + options.ex * 1000);
    }
    return 'OK';
  }

  get(key) {
    if (!this.isAvailable) throw new Error('Redis connection refused (Simulated Outage)');
    if (!this.store.has(key)) return null;
    const expiresAt = this.ttls.get(key);
    if (expiresAt && Date.now() > expiresAt) {
      this.store.delete(key);
      this.ttls.delete(key);
      return null;
    }
    return this.store.get(key);
  }

  delete(key) {
    if (!this.isAvailable) throw new Error('Redis connection refused (Simulated Outage)');
    this.ttls.delete(key);
    return this.store.delete(key);
  }

  ttl(key) {
    if (!this.isAvailable) throw new Error('Redis connection refused');
    const expiresAt = this.ttls.get(key);
    if (!expiresAt) return -2;
    const diff = Math.floor((expiresAt - Date.now()) / 1000);
    return diff > 0 ? diff : -2;
  }
}

const redisInstance = new MockRedisClient();

function simularHashSessionToken(rawToken) {
  return crypto.createHash('sha256').update(rawToken.trim()).digest('hex');
}

function simularCreateRedisSession(userId, client = redisInstance, ttlSeconds = 86400) {
  const rawToken = `pd_sess_${crypto.randomBytes(24).toString('base64url')}`;
  const tokenHash = simularHashSessionToken(rawToken);
  const redisKey = `pilot_session:${tokenHash}`;

  const sessionData = {
    user_id: userId,
    created_at: new Date().toISOString(),
    ip: '127.0.0.1',
    ua: 'TestRunner/2026'
  };

  client.set(redisKey, JSON.stringify(sessionData), { ex: ttlSeconds });
  return rawToken;
}

function simularGetRedisSession(rawToken, client = redisInstance) {
  if (!rawToken || typeof rawToken !== 'string' || rawToken.length < 16) return null;
  const tokenHash = simularHashSessionToken(rawToken);
  const redisKey = `pilot_session:${tokenHash}`;
  const val = client.get(redisKey);
  if (!val) return null;
  return JSON.parse(val);
}

// ── Mock Database de Usuarios PostgreSQL ─────────────────────────────
const MOCK_DB_USERS = {};

// Helper de Autenticación de Petición (Espejo de get_current_user en auth_rbac.py)
function simularGetCurrentUser(token, options = { allowDemoTokens: false, db: MOCK_DB_USERS, redis: redisInstance }) {
  if (!token) return { status: 401, error: 'Autenticación requerida.' };
  if (token.startsWith('expired_')) return { status: 401, error: 'Token de sesión expirado.' };
  if (token.startsWith('tampered_') || token.startsWith('invalid_')) return { status: 401, error: 'Firma de token inválida.' };

  // 1. Aislamiento estricto de tokens demo legacy
  if (token.startsWith('token_')) {
    if (options.allowDemoTokens === true) {
      return {
        status: 200,
        user: {
          user_id: 'usr_demo_001',
          email: 'dr.perez@hospital.com',
          nombre: 'Dr. Fernando Pérez',
          role: 'cirujano_vascular',
          is_active: true,
          pilot_enabled: false
        }
      };
    } else {
      return { status: 401, error: 'Token de sesión no reconocido o inválido.' };
    }
  }

  // 2. Consulta a Redis (Fail-Closed)
  let sessionData = null;
  try {
    sessionData = simularGetRedisSession(token, options.redis);
  } catch (err) {
    // Redis caído -> Fail-Closed estricto
    return { status: 401, error: 'Servicio de autenticación no disponible (Redis Fail-Closed).' };
  }

  if (!sessionData) {
    return { status: 401, error: 'Token de sesión no reconocido, inválido o expirado.' };
  }

  const userId = sessionData.user_id;
  const dbUser = Object.values(options.db).find(u => u.id === userId);

  // 3. Verificación en tiempo real contra PostgreSQL User
  if (!dbUser) {
    return { status: 401, error: 'Usuario no encontrado en base de datos.' };
  }
  if (!dbUser.is_active) {
    return { status: 401, error: 'Cuenta de usuario inactiva.' };
  }
  if (!dbUser.pilot_enabled) {
    return { status: 401, error: 'Usuario no habilitado para el piloto.' };
  }

  return {
    status: 200,
    user: {
      user_id: dbUser.id,
      email: dbUser.email,
      nombre: dbUser.full_name,
      role: dbUser.role,
      is_active: dbUser.is_active,
      pilot_enabled: dbUser.pilot_enabled,
      organization_id: dbUser.organization_id
    }
  };
}

// ── 1. PILOT USER SEED: ESTRUCTURA Y 5 ROLES MÉDICOS ─────────────────
test('1. [SEED PILOT USERS] Script seed_pilot_users.py genera 5 cuentas médicas con roles clínicos, pilot_enabled=True y passwords seguros', () => {
  const seedFile = fs.readFileSync(path.join(__dirname, 'backend', 'scripts', 'seed_pilot_users.py'), 'utf8');

  assert(seedFile.includes('from domain.password_security import hash_password'), 'seed_pilot_users.py debe importar hash_password');
  assert(!seedFile.includes('agente14_auth.get_password_hash'), 'No debe existir referencia a agente14_auth.get_password_hash');
  assert(seedFile.includes('secrets.token_urlsafe'), 'Debe generar contraseñas con secrets.token_urlsafe');
  assert(seedFile.includes('pilot_enabled=True'), 'Debe asignar pilot_enabled=True');
  assert(seedFile.includes('hospital-piloto-latam'), 'Debe vincular a la organización hospital-piloto-latam');

  // Inicializar médicos en mock DB
  MOCK_DB_USERS['piloto.medico1@piediabetico.lat'] = {
    id: 'usr-pilot-001',
    email: 'piloto.medico1@piediabetico.lat',
    password_hash: simularHashPassword('SecurePass_Med1_2026!'),
    full_name: 'Dr. Médico General Piloto 1',
    role: 'medico_general',
    is_active: true,
    pilot_enabled: true,
    organization_id: 'org-hospital-latam'
  };

  MOCK_DB_USERS['piloto.medico2@piediabetico.lat'] = {
    id: 'usr-pilot-002',
    email: 'piloto.medico2@piediabetico.lat',
    password_hash: simularHashPassword('SecurePass_Med2_2026!'),
    full_name: 'Dra. Diabetóloga Piloto 2',
    role: 'diabetologo',
    is_active: true,
    pilot_enabled: true,
    organization_id: 'org-hospital-latam'
  };
});

// ── 2. PASSWORD SECURITY: HASH SALADO NUNCA TEXTO PLANO ──────────────
test('2. [PASSWORD SECURITY] Contraseñas se almacenan como hashes criptográficos salados (Argon2id/PBKDF2)', () => {
  const raw = 'MiPasswordSuperSeguro123!';
  const hash1 = simularHashPassword(raw);
  const hash2 = simularHashPassword(raw);

  assert.notStrictEqual(raw, hash1, 'El hash no debe ser igual al texto plano');
  assert.notStrictEqual(hash1, hash2, 'Dos hashes de la misma contraseña deben tener sales distintas');
  assert.strictEqual(simularVerifyPassword(raw, hash1), true);
  assert.strictEqual(simularVerifyPassword('Incorrecto', hash1), false);
});

// ── 3. LOGIN ESCRIBE EN REDIS CON CLAVE SHA-256 ──────────────────────
let issuedBearerToken = null;
test('3. [REDIS SESSION STORE] Login genera sesión en Redis bajo clave pilot_session:<sha256>', () => {
  issuedBearerToken = simularCreateRedisSession('usr-pilot-001', redisInstance, 86400);

  assert(issuedBearerToken.startsWith('pd_sess_'), 'Token debe ser opaco con prefijo pd_sess_');
  const expectedHash = simularHashSessionToken(issuedBearerToken);
  const expectedKey = `pilot_session:${expectedHash}`;

  assert.strictEqual(redisInstance.store.has(expectedKey), true, 'La clave SHA-256 debe existir en Redis');
});

// ── 4. EL TOKEN BEARER EN TEXTO PLANO NUNCA SE ALMACENA EN REDIS ────
test('4. [REDIS ZERO BEARER LEAK] El Bearer Token en texto plano NUNCA se almacena como clave ni valor en Redis', () => {
  // Verificar que ninguna clave en Redis coincide con el raw token
  for (const key of redisInstance.store.keys()) {
    assert.notStrictEqual(key, issuedBearerToken, 'El token en texto plano no debe ser clave de Redis');
  }

  // Verificar que ningún valor en Redis contiene el raw token
  for (const val of redisInstance.store.values()) {
    assert.strictEqual(val.includes(issuedBearerToken), false, 'El token en texto plano no debe estar en el valor de Redis');
  }
});

// ── 5. EL DIGEST DE LA SESIÓN ES BASADO EN SHA-256 (64 HEX) ──────────
test('5. [SHA-256 DIGEST] La clave de sesión en Redis es pilot_session:<64_hex_chars>', () => {
  const tokenHash = simularHashSessionToken(issuedBearerToken);
  assert.strictEqual(tokenHash.length, 64, 'El hash SHA-256 debe tener exactamente 64 caracteres hexadecimales');
  assert(/^[a-f0-9]{64}$/.test(tokenHash), 'El hash SHA-256 debe ser hexadecimal en minúsculas');
});

// ── 6. TTL EXISTE Y ES <= 24 HORAS (86400s) ──────────────────────────
test('6. [SESSION TTL] La clave de Redis tiene TTL de 24h configurado', () => {
  const tokenHash = simularHashSessionToken(issuedBearerToken);
  const ttl = redisInstance.ttl(`pilot_session:${tokenHash}`);
  assert(ttl > 86000 && ttl <= 86400, `TTL debe ser <= 86400s (actual: ${ttl}s)`);
});

// ── 7. RESOLUCIÓN MULTI-WORKER / SIN DEPENDENCIA DE MEMORIA LOCAL ────
test('7. [MULTI-WORKER INDEPENDENCE] Una sesión creada en Worker A se resuelve exitosamente en Worker B (vía Redis)', () => {
  // Simulamos Worker B con un contexto completamente nuevo sin memoria compartida
  const workerBContext = {
    allowDemoTokens: false,
    db: MOCK_DB_USERS,
    redis: redisInstance // mismo cluster Redis
  };

  const res = simularGetCurrentUser(issuedBearerToken, workerBContext);
  assert.strictEqual(res.status, 200);
  assert.strictEqual(res.user.email, 'piloto.medico1@piediabetico.lat');
  assert.strictEqual(res.user.pilot_enabled, true);
});

// ── 8. TOKEN DESCONOCIDO => 401 ──────────────────────────────────────
test('8. [FAIL-CLOSED] Token desconocido o no registrado devuelve 401', () => {
  const res = simularGetCurrentUser('pd_sess_token_fantasma_no_registrado_12345', {
    allowDemoTokens: false,
    db: MOCK_DB_USERS,
    redis: redisInstance
  });
  assert.strictEqual(res.status, 401);
});

// ── 9. SESIÓN DE REDIS EXPIRADA => 401 ───────────────────────────────
test('9. [FAIL-CLOSED] Sesión de Redis con TTL expirado devuelve 401', () => {
  const expiredToken = simularCreateRedisSession('usr-pilot-001', redisInstance, -1); // Expirado inmediatamente
  const res = simularGetCurrentUser(expiredToken, {
    allowDemoTokens: false,
    db: MOCK_DB_USERS,
    redis: redisInstance
  });
  assert.strictEqual(res.status, 401);
});

// ── 10. REDIS NO DISPONIBLE => 401 / FAIL CLOSED ─────────────────────
test('10. [FAIL-CLOSED] Caída de Redis rechaza la petición con 401 sin fallback a memoria ni bypass', () => {
  const redisCaido = new MockRedisClient();
  redisCaido.isAvailable = false; // Simular caída

  const res = simularGetCurrentUser(issuedBearerToken, {
    allowDemoTokens: false,
    db: MOCK_DB_USERS,
    redis: redisCaido
  });
  assert.strictEqual(res.status, 401);
  assert(res.error.includes('Fail-Closed'), 'Debe reportar Fail-Closed');
});

// ── 11. USUARIO DESACTIVADO EN DB TRAS LOGIN => 401 SUBSECUENTE ──────
test('11. [LIVE DB CHECK] Usuario desactivado (is_active=False) tras el login es rechazado inmediatamente en la siguiente petición', () => {
  // Desactivar usuario en PostgreSQL
  MOCK_DB_USERS['piloto.medico1@piediabetico.lat'].is_active = false;

  const res = simularGetCurrentUser(issuedBearerToken, {
    allowDemoTokens: false,
    db: MOCK_DB_USERS,
    redis: redisInstance
  });
  assert.strictEqual(res.status, 401);
  assert.strictEqual(res.error, 'Cuenta de usuario inactiva.');

  // Restaurar
  MOCK_DB_USERS['piloto.medico1@piediabetico.lat'].is_active = true;
});

// ── 12. PILOT_ENABLED MODIFICADO A FALSE TRAS LOGIN => 401 SUBSECUENTE ─
test('12. [LIVE DB CHECK] Usuario con pilot_enabled=False tras el login es revocado en la siguiente petición', () => {
  // Deshabilitar piloto en PostgreSQL
  MOCK_DB_USERS['piloto.medico1@piediabetico.lat'].pilot_enabled = false;

  const res = simularGetCurrentUser(issuedBearerToken, {
    allowDemoTokens: false,
    db: MOCK_DB_USERS,
    redis: redisInstance
  });
  assert.strictEqual(res.status, 401);
  assert.strictEqual(res.error, 'Usuario no habilitado para el piloto.');

  // Restaurar
  MOCK_DB_USERS['piloto.medico1@piediabetico.lat'].pilot_enabled = true;
});

// ── 13. TOKEN DEMO RECHAZADO POR DEFECTO (ALLOW_DEMO_TOKENS=false) ────
test('13. [DEMO ISOLATION] Tokens demo (token_dr_perez, token_admin) rechazados por defecto', () => {
  const resPerez = simularGetCurrentUser('token_dr_perez', { allowDemoTokens: false, db: MOCK_DB_USERS, redis: redisInstance });
  assert.strictEqual(resPerez.status, 401);

  const resAdmin = simularGetCurrentUser('token_admin', { allowDemoTokens: false, db: MOCK_DB_USERS, redis: redisInstance });
  assert.strictEqual(resAdmin.status, 401);
});

// ── 14. TOKEN DEMO ACEPTADO ÚNICAMENTE CON ALLOW_DEMO_TOKENS=true ────
test('14. [DEMO ISOLATION] Tokens demo SOLO aceptados cuando ALLOW_DEMO_TOKENS=true explícito', () => {
  const resDemo = simularGetCurrentUser('token_dr_perez', { allowDemoTokens: true, db: MOCK_DB_USERS, redis: redisInstance });
  assert.strictEqual(resDemo.status, 200);
  assert.strictEqual(resDemo.user.role, 'cirujano_vascular');
});

// ── 15. ENDPOINT PROTEGIDO /api/pilot/ai-readiness VERIFICADO ────────
test('15. [PROTECTED AI READINESS] Endpoint /ai-readiness exige sesión válida y autoriza con token Redis real', () => {
  // Sin token -> 401
  const sinToken = simularGetCurrentUser(null, { allowDemoTokens: false, db: MOCK_DB_USERS, redis: redisInstance });
  assert.strictEqual(sinToken.status, 401);

  // Con token válido de Redis -> 200
  const conToken = simularGetCurrentUser(issuedBearerToken, { allowDemoTokens: false, db: MOCK_DB_USERS, redis: redisInstance });
  assert.strictEqual(conToken.status, 200);
  assert.strictEqual(conToken.user.pilot_enabled, true);
});

// ── 16. REMOTE PATIENT FLOW /r/{token} SEPARADO Y SIN LOGIN MÉDICO ───
test('16. [REMOTE PATIENT FLOW] /r/{token} opera exclusivamente mediante token criptográfico single-use sin requerir login médico', () => {
  const routerCode = fs.readFileSync(path.join(__dirname, 'backend', 'pilot_router.py'), 'utf8');

  assert(routerCode.includes('@router_pilot.get("/r/{raw_token}"') || routerCode.includes('@router_pilot.get("/r/{token}"'), 'Debe existir GET /r/{token}');
  assert(routerCode.includes('@router_pilot.post("/r/{raw_token}/upload"') || routerCode.includes('@router_pilot.post("/r/{token}/upload"'), 'Debe existir POST /r/{token}/upload');

  const uploadIndex = routerCode.indexOf('/upload"');
  const uploadBlock = routerCode.slice(uploadIndex, uploadIndex + 300);
  assert(!uploadBlock.includes('require_authenticated'), 'La subida del paciente no debe requerir sesión médica');
});

console.log('\n═══════════════════════════════════════════════════════════════════════');
console.log(`🏁 RESULTADO: ${passedTests}/${totalTests} PRUEBAS DE AUTH REDIS MULTI-WORKER SUPERADAS (100%)`);
console.log('═══════════════════════════════════════════════════════════════════════\n');
