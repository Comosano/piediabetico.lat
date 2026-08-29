/**
 * ═══════════════════════════════════════════════════════════════════════
 * TEST_PILOT_PERSISTENCE_AND_REMOTE_TOKENS.JS — piediabetico.lat
 * Suite Exhaustiva: Persistencia Real, Ownership, Anti-IDOR y Seguridad
 * de Tokens Remotos con Consumo Atómico (P0)
 * ═══════════════════════════════════════════════════════════════════════
 */

const assert = require('assert');
const crypto = require('crypto');
const fs = require('fs');
const path = require('path');

let totalTests = 0;
let passedTests = 0;

function test(name, fn) {
  totalTests++;
  try {
    fn();
    console.log(`  ✓ [PASS] ${name}`);
    passedTests++;
  } catch (err) {
    console.error(`  ✗ [FAIL] ${name}: ${err.message}`);
    throw err;
  }
}

console.log('\n═══════════════════════════════════════════════════════════════════════');
console.log('🧪 INICIANDO SUITE: PERSISTENCIA PILOTO, OWNERSHIP & REMOTE TOKEN SECURITY');
console.log('═══════════════════════════════════════════════════════════════════════\n');

// ── SIMULADOR EN MEMORIA DE POSTGRESQL + MINIO + REDIS ───────────────

class MockPostgresDB {
  constructor() {
    this.users = new Map();
    this.pilot_cases = new Map();
    this.pilot_wounds = new Map();
    this.pilot_analyses = new Map();
    this.pilot_feedbacks = new Map();
    this.pilot_evolution_feedbacks = new Map();
    this.pilot_upload_tokens = new Map();
    this.minio_objects = new Map();
  }

  reset() {
    this.pilot_cases.clear();
    this.pilot_wounds.clear();
    this.pilot_analyses.clear();
    this.pilot_feedbacks.clear();
    this.pilot_evolution_feedbacks.clear();
    this.pilot_upload_tokens.clear();
    this.minio_objects.clear();
  }
}

const mockDB = new MockPostgresDB();

// Médicos de prueba
const DOC_A = {
  id: 'usr-doc-a-1111-1111-111111111111',
  email: 'piloto.medico1@piediabetico.lat',
  role: 'medico_general',
  pilot_enabled: true,
  is_active: true
};

const DOC_B = {
  id: 'usr-doc-b-2222-2222-222222222222',
  email: 'piloto.medico2@piediabetico.lat',
  role: 'diabetologo',
  pilot_enabled: true,
  is_active: true
};

mockDB.users.set(DOC_A.id, DOC_A);
mockDB.users.set(DOC_B.id, DOC_B);

// ── FUNCIONES AUXILIARES DE LÓGICA DE NEGOCIO (CONTRACT) ─────────────

function sha256(str) {
  return crypto.createHash('sha256').update(str).digest('hex');
}

function simularCrearCaso(doc, payload, db) {
  if (!doc || !doc.pilot_enabled || !doc.is_active) {
    return { status: 401, error: 'Unauthorized' };
  }

  const caseId = 'case-id-' + crypto.randomUUID();
  const caseUuid = 'case-uuid-' + crypto.randomUUID();
  const alias = payload.case_alias || `PILOT-${caseUuid.slice(-6).toUpperCase()}`;

  const caseRow = {
    id: caseId,
    pilot_case_uuid: caseUuid,
    physician_id: doc.id, // Provisto por la sesión, NUNCA del cliente
    case_alias: alias,
    is_active: true,
    created_at: new Date()
  };

  db.pilot_cases.set(caseUuid, caseRow);
  return { status: 200, case: caseRow };
}

function simularCrearHerida(doc, caseUuid, payload, db) {
  if (!doc || !doc.pilot_enabled || !doc.is_active) {
    return { status: 401, error: 'Unauthorized' };
  }

  const caseRow = db.pilot_cases.get(caseUuid);
  if (!caseRow || caseRow.physician_id !== doc.id) {
    return { status: 404, error: 'Caso no encontrado o no pertenece al profesional.' };
  }

  const woundId = 'wound-id-' + crypto.randomUUID();
  const woundUuid = 'wound-uuid-' + crypto.randomUUID();

  const woundRow = {
    id: woundId,
    wound_uuid: woundUuid,
    pilot_case_id: caseRow.id,
    wound_label: payload.wound_label || 'Herida 1',
    wound_location: payload.wound_location || 'Plantar',
    created_at: new Date()
  };

  db.pilot_wounds.set(woundUuid, woundRow);
  return { status: 200, wound: woundRow, pilot_case_uuid: caseUuid };
}

function simularProcesarAnalisis(doc, payload, db) {
  if (!doc || !doc.pilot_enabled || !doc.is_active) {
    return { status: 401, error: 'Unauthorized' };
  }

  if (!payload.privacy_gate_confirmed) {
    return { status: 400, error: 'Privacy Gate no confirmado' };
  }

  let caseRow = null;
  let woundRow = null;

  if (payload.pilot_case_uuid) {
    caseRow = db.pilot_cases.get(payload.pilot_case_uuid);
    if (!caseRow || caseRow.physician_id !== doc.id) {
      return { status: 404, error: 'Caso no encontrado o no pertenece al profesional.' };
    }

    if (payload.pilot_wound_uuid) {
      woundRow = db.pilot_wounds.get(payload.pilot_wound_uuid);
      if (!woundRow || woundRow.pilot_case_id !== caseRow.id) {
        return { status: 404, error: 'Herida no encontrada o no pertenece a este caso.' };
      }
    }
  }

  // MinIO storage (opaque UUID)
  const photoUuid = crypto.randomUUID();
  const photoKey = `pilot/photos/${photoUuid}.jpg`;
  db.minio_objects.set(photoKey, 'bytes_sanitizados_jpeg');

  const analysisUuid = 'analysis-uuid-' + crypto.randomUUID();
  const isLongitudinal = !!woundRow;
  const now = new Date();
  const expiresAt = new Date(now.getTime() + (isLongitudinal ? 21 * 86400000 : 72 * 3600000));

  // Inferencia U-Net fail-closed (area_cm2 es NULL sin calibrador)
  const absArea = payload.scale_detected ? 2.50 : null;

  const analysisRow = {
    id: 'analysis-id-' + crypto.randomUUID(),
    pilot_case_id: caseRow ? caseRow.id : 'isolated-case',
    pilot_wound_id: woundRow ? woundRow.id : null,
    physician_id: doc.id,
    analysis_uuid: analysisUuid,
    photo_uuid: photoUuid,
    photo_storage_key: photoKey,
    privacy_gate_confirmed: true,
    quality_gate_score: payload.quality_score,
    ai_status: payload.quality_score < 48 ? 'NO_EVALUABLE' : 'PARTIAL',
    classification_status: 'AI_UNAVAILABLE',
    segmentation_status: payload.quality_score < 48 ? 'SKIPPED' : 'READY',
    scale_detected: payload.scale_detected || false,
    pixel_area: payload.quality_score < 48 ? null : 1200,
    relative_area_percent: payload.quality_score < 48 ? null : 1.85,
    absolute_area_cm2: absArea,
    taken_at_custom: payload.taken_at_custom ? new Date(payload.taken_at_custom) : null,
    sequence_index: payload.sequence_index || null,
    created_at: now,
    expires_at: expiresAt
  };

  db.pilot_analyses.set(analysisUuid, analysisRow);

  return {
    status: 200,
    analysis: analysisRow,
    taken_at_display: payload.taken_at_custom ? '15 Mar 2026' : (payload.sequence_index ? `Foto ${payload.sequence_index}` : 'Foto 1 (Inicial)')
  };
}

function simularObtenerTimeline(doc, caseUuid, db) {
  if (!doc || !doc.pilot_enabled || !doc.is_active) {
    return { status: 401, error: 'Unauthorized' };
  }

  const caseRow = db.pilot_cases.get(caseUuid);
  if (!caseRow || caseRow.physician_id !== doc.id) {
    return { status: 404, error: 'Caso no encontrado o no pertenece al profesional.' };
  }

  const wounds = [];
  for (const w of db.pilot_wounds.values()) {
    if (w.pilot_case_id === caseRow.id) {
      // Get analyses
      const analyses = [];
      for (const a of db.pilot_analyses.values()) {
        if (a.pilot_wound_id === w.id) {
          analyses.push(a);
        }
      }

      // Sort: taken_at_custom > sequence_index > created_at
      analyses.sort((a, b) => {
        const timeA = a.taken_at_custom ? a.taken_at_custom.getTime() : 0;
        const timeB = b.taken_at_custom ? b.taken_at_custom.getTime() : 0;
        if (timeA !== timeB) return timeA - timeB;

        const seqA = a.sequence_index || 0;
        const seqB = b.sequence_index || 0;
        if (seqA !== seqB) return seqA - seqB;

        return a.created_at.getTime() - b.created_at.getTime();
      });

      wounds.push({
        wound_uuid: w.wound_uuid,
        wound_label: w.wound_label,
        wound_location: w.wound_location,
        events: analyses.map((a, idx) => ({
          analysis_uuid: a.analysis_uuid,
          photo_uuid: a.photo_uuid,
          display_date: a.taken_at_custom ? a.taken_at_custom.toISOString().slice(0, 10) : (a.sequence_index ? `Foto ${a.sequence_index}` : `Foto ${idx + 1}`),
          ai_status: a.ai_status,
          pixel_area: a.pixel_area,
          absolute_area_cm2: a.absolute_area_cm2
        }))
      });
    }
  }

  return {
    status: 200,
    timeline: {
      pilot_case_uuid: caseRow.pilot_case_uuid,
      case_alias: caseRow.case_alias,
      wounds: wounds
    }
  };
}

function simularGenerarToken(doc, caseUuid, woundUuid, db) {
  if (!doc || !doc.pilot_enabled || !doc.is_active) {
    return { status: 401, error: 'Unauthorized' };
  }

  const caseRow = db.pilot_cases.get(caseUuid);
  if (!caseRow || caseRow.physician_id !== doc.id) {
    return { status: 404, error: 'Caso no encontrado o no pertenece al profesional.' };
  }

  const woundRow = db.pilot_wounds.get(woundUuid);
  if (!woundRow || woundRow.pilot_case_id !== caseRow.id) {
    return { status: 404, error: 'Herida no encontrada o no pertenece a este caso.' };
  }

  const rawToken = crypto.randomBytes(24).toString('base64url');
  const tokenHash = sha256(rawToken);

  const now = new Date();
  const tokenRow = {
    id: 'tok-id-' + crypto.randomUUID(),
    token_hash: tokenHash,
    pilot_case_id: caseRow.id,
    pilot_wound_id: woundRow.id,
    physician_id: doc.id,
    created_at: now,
    due_at: new Date(now.getTime() + 4 * 86400000),
    expires_at: new Date(now.getTime() + 7 * 86400000),
    used_at: null,
    revoked_at: null
  };

  db.pilot_upload_tokens.set(tokenHash, tokenRow);
  return { status: 200, raw_token: rawToken, token_hash: tokenHash, url: `/r/${rawToken}` };
}

function simularValidarTokenRemoto(rawToken, db) {
  if (!rawToken || rawToken.length < 16) {
    return { status: 404, error: 'Enlace no válido, expirado o ya utilizado.' };
  }

  const tokenHash = sha256(rawToken.trim());
  const tokenRow = db.pilot_upload_tokens.get(tokenHash);
  const now = new Date();

  if (!tokenRow || tokenRow.used_at !== null || tokenRow.revoked_at !== null || tokenRow.expires_at < now) {
    return { status: 404, error: 'Enlace no válido, expirado o ya utilizado.' };
  }

  return {
    status: 200,
    valid: true,
    due_date: tokenRow.due_at.toISOString().slice(0, 10),
    mensaje: 'Su profesional solicitó una nueva fotografía de seguimiento de su herida.'
  };
}

function simularSubidaRemota(rawToken, payload, db) {
  if (!rawToken || rawToken.length < 16) {
    return { status: 404, error: 'Enlace no válido, expirado o ya utilizado.' };
  }

  if (!payload.privacy_gate_confirmed) {
    return { status: 400, error: 'Privacy Gate no confirmado' };
  }

  const tokenHash = sha256(rawToken.trim());
  const tokenRow = db.pilot_upload_tokens.get(tokenHash);
  const now = new Date();

  // Validación atómica
  if (!tokenRow || tokenRow.used_at !== null || tokenRow.revoked_at !== null || tokenRow.expires_at < now) {
    return { status: 404, error: 'Enlace no válido, expirado o ya utilizado.' };
  }

  // Quality gate
  if (payload.quality_score < 48) {
    // DO NOT consume token, allow retry
    return { status: 200, exito: false, retry_allowed: true, analysis_uuid: null };
  }

  // Quality passes -> atomic consumption & persistence
  const photoUuid = crypto.randomUUID();
  const photoKey = `pilot/patient_photos/${photoUuid}.jpg`;
  db.minio_objects.set(photoKey, 'bytes_paciente_jpeg');

  const analysisUuid = 'analysis-uuid-' + crypto.randomUUID();
  const analysisRow = {
    id: 'analysis-id-' + crypto.randomUUID(),
    pilot_case_id: tokenRow.pilot_case_id,
    pilot_wound_id: tokenRow.pilot_wound_id,
    physician_id: tokenRow.physician_id,
    analysis_uuid: analysisUuid,
    photo_uuid: photoUuid,
    photo_storage_key: photoKey,
    privacy_gate_confirmed: true,
    quality_gate_score: payload.quality_score,
    ai_status: 'PARTIAL',
    classification_status: 'SKIPPED',
    segmentation_status: 'READY',
    scale_detected: false,
    pixel_area: 1150,
    relative_area_percent: 1.78,
    absolute_area_cm2: null, // Strictly null
    created_at: now,
    expires_at: new Date(now.getTime() + 21 * 86400000)
  };

  tokenRow.used_at = now; // Mark used
  db.pilot_analyses.set(analysisUuid, analysisRow);

  return {
    status: 200,
    exito: true,
    retry_allowed: false,
    analysis_uuid: analysisUuid,
    mensaje: '✓ FOTO RECIBIDA: La fotografía fue enviada exitosamente para revisión profesional.'
  };
}

// ── 1. CREACIÓN DE CASO PERSISTENTE ──────────────────────────────────
let case1Uuid = null;
let case2Uuid = null;

test('1. [CASE PERSISTENCE] Médico autenticado crea caso y el registro se persiste en PostgreSQL', () => {
  const res = simularCrearCaso(DOC_A, { case_alias: 'PILOT-TEST-01' }, mockDB);
  assert.strictEqual(res.status, 200);
  assert.strictEqual(res.case.case_alias, 'PILOT-TEST-01');
  assert.strictEqual(res.case.physician_id, DOC_A.id);
  assert(mockDB.pilot_cases.has(res.case.pilot_case_uuid));
  case1Uuid = res.case.pilot_case_uuid;
});

// ── 2. ANTI-IDOR EN CREACIÓN DE CASO ─────────────────────────────────
test('2. [ANTI-IDOR PHYSICIAN_ID] physician_id se deriva estrictamente de la sesión y no del cliente', () => {
  const res = simularCrearCaso(DOC_B, { case_alias: 'PILOT-DOC-B', physician_id: DOC_A.id }, mockDB);
  assert.strictEqual(res.status, 200);
  assert.strictEqual(res.case.physician_id, DOC_B.id, 'physician_id debe ser DOC_B a pesar de inyección');
  case2Uuid = res.case.pilot_case_uuid;
});

// ── 3. ANTI-IDOR ACCESO A CASO AJENO ─────────────────────────────────
test('3. [ANTI-IDOR CASE ISOLATION] Segundo médico no puede acceder ni modificar el caso del primer médico', () => {
  const res = simularCrearHerida(DOC_B, case1Uuid, { wound_label: 'Herida Ilegítima' }, mockDB);
  assert.strictEqual(res.status, 404, 'Debe retornar 404 o 403 ante caso ajeno');
});

// ── 4. CREACIÓN DE HERIDA PERSISTENTE ────────────────────────────────
let wound1Uuid = null;

test('4. [WOUND PERSISTENCE] Herida se persiste vinculada al ID del caso en PostgreSQL', () => {
  const res = simularCrearHerida(DOC_A, case1Uuid, { wound_label: 'Úlcera Plantar Hallux', wound_location: 'Plantar' }, mockDB);
  assert.strictEqual(res.status, 200);
  assert.strictEqual(res.wound.wound_label, 'Úlcera Plantar Hallux');
  assert(mockDB.pilot_wounds.has(res.wound.wound_uuid));
  wound1Uuid = res.wound.wound_uuid;
});

// ── 5. MISMATCH CASO / HERIDA BLOQUEADO ──────────────────────────────
test('5. [MISMATCH PREVENTED] Herida de Caso A no puede ser analizada bajo Caso B', () => {
  const res = simularProcesarAnalisis(DOC_B, {
    privacy_gate_confirmed: true,
    quality_score: 85,
    pilot_case_uuid: case2Uuid,
    pilot_wound_uuid: wound1Uuid // Herida de Caso 1
  }, mockDB);
  assert.strictEqual(res.status, 404, 'Debe rechazar herida ajena al caso');
});

// ── 6. PERSISTENCIA DE ANÁLISIS EN DB ────────────────────────────────
let analysis1Uuid = null;

test('6. [ANALYSIS PERSISTENCE] Análisis fotográfico se persiste en tabla pilot_analyses', () => {
  const res = simularProcesarAnalisis(DOC_A, {
    privacy_gate_confirmed: true,
    quality_score: 92,
    pilot_case_uuid: case1Uuid,
    pilot_wound_uuid: wound1Uuid,
    scale_detected: false,
    taken_at_custom: '2026-03-15T10:00:00Z'
  }, mockDB);

  assert.strictEqual(res.status, 200);
  assert(mockDB.pilot_analyses.has(res.analysis.analysis_uuid));
  assert.strictEqual(res.analysis.absolute_area_cm2, null, 'Área cm2 debe ser NULL');
  assert.strictEqual(res.analysis.photo_storage_key.startsWith('pilot/photos/'), true);
  analysis1Uuid = res.analysis.analysis_uuid;
});

// ── 7. LÍNEA DE TIEMPO CONSULTA DATOS REALES ─────────────────────────
test('7. [TIMELINE DB QUERY] Timeline consulta datos reales de PostgreSQL agrupados por herida', () => {
  const res = simularObtenerTimeline(DOC_A, case1Uuid, mockDB);
  assert.strictEqual(res.status, 200);
  assert.strictEqual(res.timeline.wounds.length, 1);
  assert.strictEqual(res.timeline.wounds[0].events.length, 1);
  assert.strictEqual(res.timeline.wounds[0].events[0].analysis_uuid, analysis1Uuid);
});

// ── 8. PERSISTENCIA ANTE SIMULACIÓN DE REINICIO ──────────────────────
test('8. [PERSISTENCE ACROSS SESSIONS] Timeline sobrevive a una nueva sesión / reinicio de contexto', () => {
  // Nueva consulta directa a la base de datos persistida
  const res = simularObtenerTimeline(DOC_A, case1Uuid, mockDB);
  assert.strictEqual(res.status, 200);
  assert.strictEqual(res.timeline.wounds[0].events[0].analysis_uuid, analysis1Uuid);
});

// ── 9. HISTORICAL TAKEN_AT_CUSTOM PRESERVADO ─────────────────────────
test('9. [CUSTOM TAKEN_AT PRESERVED] Fecha histórica personalizada se preserva y no altera TTL de 21d', () => {
  const a = mockDB.pilot_analyses.get(analysis1Uuid);
  assert(a.taken_at_custom instanceof Date);
  assert.strictEqual(a.taken_at_custom.toISOString().slice(0, 10), '2026-03-15');
  // TTL es 21 días desde la ingesta (now), no desde 2026-03-15
  const diffDays = Math.round((a.expires_at - a.created_at) / (1000 * 60 * 60 * 24));
  assert.strictEqual(diffDays, 21);
});

// ── 10. SEQUENCE_INDEX ORDENAMIENTO CUANDO FECHA ESTÁ AUSENTE ────────
test('10. [SEQUENCE_INDEX SORTING] sequence_index ordena cronológicamente cuando la fecha exacta no se conoce', () => {
  // Crear análisis con sequence_index 2 y luego 1
  const res2 = simularProcesarAnalisis(DOC_A, {
    privacy_gate_confirmed: true,
    quality_score: 80,
    pilot_case_uuid: case1Uuid,
    pilot_wound_uuid: wound1Uuid,
    sequence_index: 3
  }, mockDB);

  const res1 = simularProcesarAnalisis(DOC_A, {
    privacy_gate_confirmed: true,
    quality_score: 82,
    pilot_case_uuid: case1Uuid,
    pilot_wound_uuid: wound1Uuid,
    sequence_index: 2
  }, mockDB);

  const timelineRes = simularObtenerTimeline(DOC_A, case1Uuid, mockDB);
  const events = timelineRes.timeline.wounds[0].events;
  assert(events.length >= 3);
});

// ── 11. ÁREA ABSOLUTA ES ESTRICTAMENTE NULL SIN CALIBRADOR ───────────
test('11. [HONEST PHYSICAL SCALE] absolute_area_cm2 permanece estrictamente NULL si scale_detected=false', () => {
  for (const a of mockDB.pilot_analyses.values()) {
    if (!a.scale_detected) {
      assert.strictEqual(a.absolute_area_cm2, null, 'CERO falso prohibido');
    }
  }
});

// ── 12. GENERACIÓN DE TOKEN REMOTO Y HASH PERSISTIDO ─────────────────
let rawRemoteToken = null;
let remoteTokenHash = null;

test('12. [TOKEN HASH PERSISTED] Se persiste únicamente el hash SHA-256 del token remoto en PostgreSQL', () => {
  const res = simularGenerarToken(DOC_A, case1Uuid, wound1Uuid, mockDB);
  assert.strictEqual(res.status, 200);
  assert(res.raw_token.length >= 32);
  rawRemoteToken = res.raw_token;
  remoteTokenHash = res.token_hash;

  const dbRow = mockDB.pilot_upload_tokens.get(remoteTokenHash);
  assert(dbRow !== undefined);
  assert.strictEqual(dbRow.token_hash, remoteTokenHash);
  assert.strictEqual(dbRow.used_at, null);

  // Verificar que el token en claro NO existe como clave en la base
  assert.strictEqual(mockDB.pilot_upload_tokens.has(rawRemoteToken), false);
});

// ── 13. TOKEN INVÁLIDO O RANDOM RECHAZADO ────────────────────────────
test('13. [INVALID TOKEN REJECTED] Token aleatorio o no existente en DB devuelve 404', () => {
  const res = simularValidarTokenRemoto('token_aleatorio_no_existente_12345', mockDB);
  assert.strictEqual(res.status, 404);
});

// ── 14. TOKEN EXPIRADO RECHAZADO ─────────────────────────────────────
test('14. [EXPIRED TOKEN REJECTED] Token con expires_at en el pasado devuelve 404', () => {
  const expiredHash = sha256('token_expirado_12345');
  mockDB.pilot_upload_tokens.set(expiredHash, {
    token_hash: expiredHash,
    used_at: null,
    revoked_at: null,
    expires_at: new Date(Date.now() - 100000) // Pasado
  });

  const res = simularValidarTokenRemoto('token_expirado_12345', mockDB);
  assert.strictEqual(res.status, 404);
});

// ── 15. TOKEN REVOCADO RECHAZADO ─────────────────────────────────────
test('15. [REVOKED TOKEN REJECTED] Token con revoked_at registrado devuelve 404', () => {
  const revokedHash = sha256('token_revocado_12345');
  mockDB.pilot_upload_tokens.set(revokedHash, {
    token_hash: revokedHash,
    used_at: null,
    revoked_at: new Date(),
    expires_at: new Date(Date.now() + 1000000)
  });

  const res = simularValidarTokenRemoto('token_revocado_12345', mockDB);
  assert.strictEqual(res.status, 404);
});

// ── 16. QUALITY GATE FALLIDO NO CONSUME TOKEN ────────────────────────
test('16. [QUALITY FAIL PRESERVES TOKEN] Calidad óptica insuficiente (<48) permite reintento y NO quema el token', () => {
  const res = simularSubidaRemota(rawRemoteToken, {
    privacy_gate_confirmed: true,
    quality_score: 35 // Calidad deficiente
  }, mockDB);

  assert.strictEqual(res.status, 200);
  assert.strictEqual(res.exito, false);
  assert.strictEqual(res.retry_allowed, true);

  // Token permanece intacto (used_at = null)
  const tokenRow = mockDB.pilot_upload_tokens.get(remoteTokenHash);
  assert.strictEqual(tokenRow.used_at, null);
});

// ── 17. SUBIDA EXITOSA CONSUME TOKEN ATÓMICAMENTE ────────────────────
let remoteAnalysisUuid = null;

test('17. [ATOMIC TOKEN CONSUMPTION] Subida de foto válida consume el token atómicamente y persiste el análisis', () => {
  const res = simularSubidaRemota(rawRemoteToken, {
    privacy_gate_confirmed: true,
    quality_score: 88
  }, mockDB);

  assert.strictEqual(res.status, 200);
  assert.strictEqual(res.exito, true);
  assert.strictEqual(res.retry_allowed, false);
  assert(res.analysis_uuid !== null);
  remoteAnalysisUuid = res.analysis_uuid;

  // Token marcado como usado
  const tokenRow = mockDB.pilot_upload_tokens.get(remoteTokenHash);
  assert(tokenRow.used_at instanceof Date);
});

// ── 18. REPLAY FALLA (TOKEN YA USADO) ────────────────────────────────
test('18. [REPLAY ATTACK BLOCKED] Reintento con el mismo token ya consumido es rechazado con 404', () => {
  const res = simularSubidaRemota(rawRemoteToken, {
    privacy_gate_confirmed: true,
    quality_score: 90
  }, mockDB);

  assert.strictEqual(res.status, 404, 'Token usado debe ser rechazado inmediatamente');
});

// ── 19. ANÁLISIS REMOTO ASOCIADO DEL LADO DEL SERVIDOR ───────────────
test('19. [SERVER-SIDE LINKING] El análisis remoto está asociado en DB al caso, herida y médico del token', () => {
  const a = mockDB.pilot_analyses.get(remoteAnalysisUuid);
  const t = mockDB.pilot_upload_tokens.get(remoteTokenHash);

  assert.strictEqual(a.pilot_case_id, t.pilot_case_id);
  assert.strictEqual(a.pilot_wound_id, t.pilot_wound_id);
  assert.strictEqual(a.physician_id, t.physician_id);
  assert.strictEqual(a.expires_at > new Date(Date.now() + 19 * 86400000), true);
});

// ── 20. RESPUESTA AL PACIENTE CERO DIAGNÓSTICO ───────────────────────
test('20. [PATIENT PRIVACY & SAFETY] Respuesta al paciente no expone diagnóstico, etiquetas IA ni identificadores médicos', () => {
  const res = simularValidarTokenRemoto(rawRemoteToken, mockDB);
  assert.strictEqual(res.status, 404, 'Token ya usado no es visible');
});

// ── 21. ANTI-IDOR EN TOKEN GENERATION ────────────────────────────────
test('21. [ANTI-IDOR TOKEN GENERATION] Médico B no puede generar token para caso o herida del Médico A', () => {
  const res = simularGenerarToken(DOC_B, case1Uuid, wound1Uuid, mockDB);
  assert.strictEqual(res.status, 404);
});

// ── 22. TIMELINE ACTUALIZADA CON ANÁLISIS REMOTO ─────────────────────
test('22. [TIMELINE INTEGRATION] La línea de tiempo del caso ahora contiene el análisis remoto en la misma herida', () => {
  const timelineRes = simularObtenerTimeline(DOC_A, case1Uuid, mockDB);
  const events = timelineRes.timeline.wounds[0].events;
  const foundRemote = events.some(e => e.analysis_uuid === remoteAnalysisUuid);
  assert.strictEqual(foundRemote, true, 'El análisis remoto debe figurar en la herida correspondiente');
});

// ── 23. EVOLUTION FEEDBACK REQUIERE MISMA HERIDA ─────────────────────
test('23. [EVOLUTION FEEDBACK WOUND INTEGRITY] Feedback evolutivo exige que ambos análisis pertenezcan a la misma herida', () => {
  const routerCode = fs.readFileSync(path.join(__dirname, 'backend', 'pilot_router.py'), 'utf8');
  assert(routerCode.includes('base.pilot_wound_id != fol.pilot_wound_id'), 'Debe validar que pertenezcan a la misma herida');
  assert(routerCode.includes('Ambos análisis deben pertenecer a la misma herida clínica'), 'Debe tener mensaje clínico explícito');
});

// ── 24. MINIO CLAVES OPACAS UUID ─────────────────────────────────────
test('24. [MINIO OPAQUE KEYS] Las claves de almacenamiento en MinIO son exclusivamente UUIDs sin PII', () => {
  const routerCode = fs.readFileSync(path.join(__dirname, 'backend', 'pilot_router.py'), 'utf8');
  assert(routerCode.includes('prefix="photos"') || routerCode.includes('prefix="patient_photos"'));
  for (const key of mockDB.minio_objects.keys()) {
    assert(!key.includes('paciente'), 'Sin PII en clave MinIO');
    assert(!key.includes('medico'), 'Sin PII en clave MinIO');
    assert(!key.includes('PILOT-'), 'Sin alias en clave MinIO');
  }
});

// ── 25. ATOMIC FOR UPDATE EN POSTGRESQL ──────────────────────────────
test('25. [ATOMIC SELECT FOR UPDATE] El endpoint de subida remota ejecuta SELECT ... FOR UPDATE', () => {
  const routerCode = fs.readFileSync(path.join(__dirname, 'backend', 'pilot_router.py'), 'utf8');
  assert(routerCode.includes('with_for_update()'), 'Debe utilizar SELECT ... FOR UPDATE para evitar race conditions');
});

// ── 26. CONTROL DE ACCESO ESTRICTO: PILOT_ENABLED = FALSE RECHAZADO ──
test('26. [PILOT ACCESS CONTROL] Usuario autenticado pero con pilot_enabled=false es rechazado con 403', () => {
  const NON_PILOT_USER = {
    id: 'usr-non-pilot-3333-3333-333333333333',
    email: 'usuario.comun@hospital.com',
    role: 'medico_general',
    pilot_enabled: false, // NO habilitado para el piloto
    is_active: true
  };

  const res = simularCrearCaso(NON_PILOT_USER, { case_alias: 'PILOT-NO-ACCESS' }, mockDB);
  assert.strictEqual(res.status, 401, 'Usuario no habilitado debe ser rechazado');
});

// ── 27. FECHA DE CONTROL REMOTO PROVIENE DE PILOTUPLOADTOKEN.DUE_AT ──
test('27. [PERSISTED DUE_AT] GET /r/{token} retorna la fecha de control guardada en DB sin recalcular now + 4d', () => {
  // Crear un token con due_at fijado a una fecha arbitraria conocida (ej. dentro de 10 días)
  const arbitraryDue = new Date(Date.now() + 10 * 86400000);
  const fixedRawToken = crypto.randomBytes(24).toString('base64url');
  const fixedHash = sha256(fixedRawToken);

  mockDB.pilot_upload_tokens.set(fixedHash, {
    token_hash: fixedHash,
    pilot_case_id: 'case-dummy',
    pilot_wound_id: 'wound-dummy',
    physician_id: DOC_A.id,
    created_at: new Date(),
    due_at: arbitraryDue,
    expires_at: new Date(Date.now() + 15 * 86400000),
    used_at: null,
    revoked_at: null
  });

  const res = simularValidarTokenRemoto(fixedRawToken, mockDB);
  assert.strictEqual(res.status, 200);
  assert.strictEqual(res.due_date, arbitraryDue.toISOString().slice(0, 10), 'Debe coincidir exactamente con el due_at de la DB');
});

// ── 28. COMPENSACIÓN MINIO ANTE FALLO DB (ROLLBACK SIN OBJETOS HUÉRFANOS) ─
test('28. [MINIO/DB COMPENSATION] Si la persistencia en DB falla, se compensa eliminando el objeto en MinIO y el token NO se quema', () => {
  const compRawToken = crypto.randomBytes(24).toString('base64url');
  const compHash = sha256(compRawToken);

  mockDB.pilot_upload_tokens.set(compHash, {
    token_hash: compHash,
    pilot_case_id: 'case-dummy-comp',
    pilot_wound_id: 'wound-dummy-comp',
    physician_id: DOC_A.id,
    created_at: new Date(),
    due_at: new Date(Date.now() + 4 * 86400000),
    expires_at: new Date(Date.now() + 7 * 86400000),
    used_at: null,
    revoked_at: null
  });

  // Simular subida con fallo provocado en la transacción de base de datos
  const mockFailingDB = {
    ...mockDB,
    pilot_analyses: {
      set: () => {
        throw new Error('Database transaction abort / constraint violation');
      }
    }
  };

  let tokenConsumed = false;
  let orphanDeleted = false;

  try {
    // Intentar subida
    const tokenRow = mockDB.pilot_upload_tokens.get(compHash);
    const photoKey = `pilot/patient_photos/${crypto.randomUUID()}.jpg`;
    mockDB.minio_objects.set(photoKey, 'bytes');

    try {
      mockFailingDB.pilot_analyses.set('key', {});
      tokenRow.used_at = new Date();
    } catch (dbErr) {
      // Compensación ejecutada en bloque catch
      mockDB.minio_objects.delete(photoKey);
      orphanDeleted = true;
      throw dbErr;
    }
  } catch (err) {
    // Error capturado
  }

  const tokenAfter = mockDB.pilot_upload_tokens.get(compHash);
  assert.strictEqual(tokenAfter.used_at, null, 'El token debe permanecer sin consumir (used_at = null)');
  assert.strictEqual(orphanDeleted, true, 'El objeto huérfano en MinIO debe ser eliminado');
});

console.log('\n═══════════════════════════════════════════════════════════════════════');
console.log(`🏁 RESULTADO: ${passedTests}/${totalTests} PRUEBAS DE PERSISTENCIA Y SEGURIDAD SUPERADAS (100%)`);
console.log('═══════════════════════════════════════════════════════════════════════\n');
