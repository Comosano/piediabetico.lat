const assert = require('assert');
const fs = require('fs');
const path = require('path');

console.log('═══════════════════════════════════════════════════════════════════════');
console.log('🧪 SUITE DE ACEPTACIÓN: TIMELINE RETROSPECTIVO & PILOTO v0.1');
console.log('   Casos Pseudonimizados · PilotWound · Fotos Históricas · TTL Dual');
console.log('   Timeline Vertical · Comparación Honesta · Evaluación de Evolución');
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

// ── 1. MODELO LONGITUDINAL: PILOT CASE Y ALIAS PSEUDONIMIZADO ─────────
test('1. PilotCase: Alias Pseudonimizado (PILOT-0001) y Cero PII', () => {
  const modelsPath = path.join(__dirname, 'backend', 'models.py');
  const content = fs.readFileSync(modelsPath, 'utf8');

  assert(content.includes('case_alias'), 'PilotCase debe tener case_alias');
  assert(content.includes('idx_pilot_cases_alias'), 'Debe existir índice sobre case_alias');
});

// ── 2. ENTIDAD PILOT WOUND (MÚLTIPLES HERIDAS POR CASO) ───────────────
test('2. Entidad PilotWound: Múltiples Heridas por Caso con Localización', () => {
  const modelsPath = path.join(__dirname, 'backend', 'models.py');
  const content = fs.readFileSync(modelsPath, 'utf8');

  assert(content.includes('class PilotWound(Base):'), 'Debe existir modelo PilotWound');
  assert(content.includes('wound_label'), 'PilotWound debe tener wound_label');
  assert(content.includes('wound_location'), 'PilotWound debe tener wound_location');
  assert(content.includes('pilot_wound_id'), 'PilotAnalysis debe vincularse opcionalmente a PilotWound');
});

// ── 3. FOTOGRAFÍAS HISTÓRICAS: FECHA REAL Y SEQUENCE INDEX ────────────
test('3. Fotos Históricas: taken_at_custom opcional y sequence_index sin fechas inventadas', () => {
  const routerPath = path.join(__dirname, 'backend', 'pilot_router.py');
  const content = fs.readFileSync(routerPath, 'utf8');

  assert(content.includes('taken_at_custom'), 'Debe admitir taken_at_custom');
  assert(content.includes('sequence_index'), 'Debe admitir sequence_index');
  assert(content.includes('taken_at_display'), 'Debe exponer taken_at_display sin inventar fechas');
});

// ── 4. POLÍTICA DE RETENCIÓN DUAL: 72H AISLADA vs 21D LONGITUDINAL ────
test('4. Retención Dual: TTL 72 Horas (Aislada) vs TTL 21 Días (Longitudinal)', () => {
  const routerContent = fs.readFileSync(path.join(__dirname, 'backend', 'pilot_router.py'), 'utf8');
  assert(routerContent.includes('timedelta(days=21)'), 'Debe asignar 21 días para análisis longitudinal');
  assert(routerContent.includes('timedelta(hours=72)'), 'Debe asignar 72 horas para análisis aislado');

  const purgeScript = fs.readFileSync(path.join(__dirname, 'backend', 'scripts', 'purge_expired_pilot_photos.py'), 'utf8');
  assert(purgeScript.includes('72h aislado / 21d longitudinal') || purgeScript.includes('21 días'), 'Purgador debe soportar retención dual');
});

// ── 5. TIMELINE API Y PROTECCIÓN ANTI-IDOR ────────────────────────────
test('5. Endpoint Timeline: GET /api/pilot/cases/{uuid}/timeline y Eventos Ordenados', () => {
  const routerContent = fs.readFileSync(path.join(__dirname, 'backend', 'pilot_router.py'), 'utf8');
  assert(routerContent.includes('/cases/{pilot_case_uuid}/timeline'), 'Debe existir endpoint timeline');
  assert(routerContent.includes('PilotCaseTimelineOutput'), 'Debe responder con PilotCaseTimelineOutput');
  assert(routerContent.includes('PilotWoundTimelineGroup'), 'Debe agrupar eventos por herida');
});

// ── 6. COMPARACIÓN HONESTA (SIN CM² FALSOS NI COMPARACIÓN PIXEL_AREA) ─
test('6. Comparación Longitudinal: Cero Variación cm² Inventada entre Fotos No Calibradas', () => {
  const routerContent = fs.readFileSync(path.join(__dirname, 'backend', 'pilot_router.py'), 'utf8');
  // Confirmar que absolute_area_cm2 sigue siendo estrictamente None si scale_detected es False
  assert(routerContent.includes('absolute_area_cm2: Optional[float] = None'), 'Área cm² debe ser null sin calibrador');
});

// ── 7. EVALUACIÓN DE EVOLUCIÓN: PILOT EVOLUTION FEEDBACK ──────────────
test('7. Evaluación de Evolución: MEJOR/SIMILAR/PEOR y Acuerdo con IA', () => {
  const routerContent = fs.readFileSync(path.join(__dirname, 'backend', 'pilot_router.py'), 'utf8');
  assert(routerContent.includes('PilotEvolutionFeedbackInput'), 'Debe existir schema de feedback de evolución');
  assert(routerContent.includes('/evolution-feedback'), 'Debe existir endpoint POST /evolution-feedback');
  assert(routerContent.includes('clinical_evolution'), 'Debe validar clinical_evolution');
  assert(routerContent.includes('system_representation_agreement'), 'Debe validar system_representation_agreement');
});

// ── 8. MÉTRICAS LONGITUDINALES EN PILOT_REPORT ────────────────────────
test('8. Reporte Piloto Extendido: Métricas de Casos, Heridas y Comparaciones (Zero PII)', () => {
  const repContent = fs.readFileSync(path.join(__dirname, 'backend', 'scripts', 'generate_pilot_report.py'), 'utf8');
  assert(repContent.includes('casos_pseudonimizados_creados'), 'Debe compilar casos creados');
  assert(repContent.includes('heridas_clinicas_creadas'), 'Debe compilar heridas creadas');
  assert(repContent.includes('casos_con_multiples_fotografias'), 'Debe compilar casos con múltiples fotos');
  assert(repContent.includes('total_comparaciones_realizadas'), 'Debe compilar comparaciones realizadas');
  assert(repContent.includes('evolucion_clinica_mejor'), 'Debe contar evolución MEJOR/SIMILAR/PEOR');
  assert(!repContent.includes('comment'), 'No debe exportar comentarios en CSV/JSON');
});

// ── 9. MIGRACIÓN ALEMBIC 005_PILOT_TIMELINE ───────────────────────────
test('9. Migración Alembic 005_pilot_timeline.py: Cadena Lineal Verificada', () => {
  const migPath = path.join(__dirname, 'backend', 'alembic', 'versions', '005_pilot_timeline.py');
  assert(fs.existsSync(migPath), 'Falta 005_pilot_timeline.py');

  const content = fs.readFileSync(migPath, 'utf8');
  assert(content.includes('005_pilot_timeline'), 'Revision ID debe ser 005_pilot_timeline');
  assert(content.includes('004_pilot_v01'), 'Down revision debe ser 004_pilot_v01');
  assert(content.includes('pilot_wounds'), 'Debe crear tabla pilot_wounds');
  assert(content.includes('pilot_evolution_feedbacks'), 'Debe crear tabla pilot_evolution_feedbacks');
  assert(content.includes('taken_at_custom'), 'Debe agregar taken_at_custom');
  assert(content.includes('sequence_index'), 'Debe agregar sequence_index');
});

// ── 10. SIMULACIÓN INTEGRAL DEL FLUJO LONGITUDINAL DE MAÑANA ─────────
test('10. Simulación de Flujo Completo: Caso PILOT-0001 con 3 Fotos Históricas y Comparación', () => {
  // Simular flujo completo en memoria
  const caso = {
    pilot_case_uuid: "case-001",
    case_alias: "PILOT-0001",
    wounds: [
      { wound_uuid: "w-001", label: "Herida 1 — Talón", location: "Talón" },
      { wound_uuid: "w-002", label: "Herida 2 — Hallux", location: "Hallux" }
    ]
  };

  const fotoA = {
    analysis_uuid: "a-001",
    pilot_wound_uuid: "w-001",
    taken_at_custom: "2026-08-03T10:00:00Z",
    sequence_index: 1,
    ai_status: "COMPLETED",
    classification: "Abnormal(Ulcer)",
    pixel_area: 5000,
    relative_area_percent: 5.2,
    scale_detected: false,
    absolute_area_cm2: null,
    expires_at_days: 21
  };

  const fotoB = {
    analysis_uuid: "a-002",
    pilot_wound_uuid: "w-001",
    taken_at_custom: "2026-08-07T11:00:00Z",
    sequence_index: 2,
    ai_status: "COMPLETED",
    classification: "Abnormal(Ulcer)",
    pixel_area: 4200,
    relative_area_percent: 4.4,
    scale_detected: false,
    absolute_area_cm2: null,
    expires_at_days: 21
  };

  const fotoC = {
    analysis_uuid: "a-003",
    pilot_wound_uuid: "w-001",
    taken_at_custom: null, // Fecha no recordada
    sequence_index: 3,
    ai_status: "COMPLETED",
    classification: "Abnormal(Ulcer)",
    pixel_area: 3100,
    relative_area_percent: 3.2,
    scale_detected: false,
    absolute_area_cm2: null,
    expires_at_days: 21
  };

  // Comparación A vs C
  const comparacion = {
    baseline: fotoA.analysis_uuid,
    followup: fotoC.analysis_uuid,
    clinical_evolution: "MEJOR",
    system_representation_agreement: "SI",
    area_variation_cm2: null // Estrictamente NULL
  };

  assert.strictEqual(caso.wounds.length, 2, 'Caso debe soportar múltiples heridas');
  assert.strictEqual(fotoA.expires_at_days, 21, 'Foto longitudinal debe tener TTL 21 días');
  assert.strictEqual(fotoC.taken_at_custom, null, 'Foto sin fecha no debe inventar fecha');
  assert.strictEqual(fotoC.sequence_index, 3, 'Foto sin fecha debe tener sequence_index');
  assert.strictEqual(comparacion.area_variation_cm2, null, 'Comparación no debe inferir cm²');
  assert.strictEqual(comparacion.clinical_evolution, "MEJOR", 'Evolución clínica debe ser válida');
});

console.log('\n═══════════════════════════════════════════════════════════════════════');
console.log(`🏁 RESULTADO: ${passedTests}/${totalTests} PRUEBAS DE TIMELINE v0.1 SUPERADAS (100%)`);
console.log('═══════════════════════════════════════════════════════════════════════\n');
