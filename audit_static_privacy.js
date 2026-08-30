const fs = require('fs');
const path = require('path');
const assert = require('assert');

const app = fs.readFileSync(path.join(__dirname, 'app.js'), 'utf8');
const index = fs.readFileSync(path.join(__dirname, 'index.html'), 'utf8');

const forbidden = [
  'case-demo-001',
  'wound-demo-001',
  'fakeAnalysisUuid',
  'Abnormal(Ulcer) · 89%',
  'piediabetico_pilot_data_v01'
];

const prohibitedStorageKeys = [
  'piediabetico_paciente_profile',
  'piediabetico_prof_profile',
  'pd_current_user',
  'AUTH_USER_KEY',
  'PACIENTES_KEY',
  'TURNOS_STORAGE_KEY',
  'piediabetico_turnos_db',
  'pd_newsletter_subs',
  'pd_consultas_contacto',
  'ultimo_analisis_paciente_ts',
  'pd_api_url'
];

console.log('═══════════════════════════════════════════════════════════════════════');
console.log('🔍 STATIC PRIVACY & ZERO-STORAGE AUDIT');
console.log('═══════════════════════════════════════════════════════════════════════\n');

let allClean = true;

forbidden.forEach(str => {
  const inApp = app.includes(str);
  const inIndex = index.includes(str);
  if (inApp || inIndex) {
    console.error(`  ✗ FAIL: Found forbidden mock string "${str}"`);
    allClean = false;
  } else {
    console.log(`  ✓ PASS: Clean of "${str}"`);
  }
});

console.log('\n--- Prohibited Storage Keys Audit ---');
prohibitedStorageKeys.forEach(key => {
  const hasProhibitedWrite = app.includes(`localStorage.setItem('${key}'`) || app.includes(`localStorage.setItem("${key}"`);
  if (hasProhibitedWrite) {
    console.error(`  ✗ FAIL: Found prohibited storage write for key "${key}"`);
    allClean = false;
  } else {
    console.log(`  ✓ PASS: Clean of prohibited storage key "${key}"`);
  }
});

const pilotStart = app.indexOf('PORTAL PILOTO v0.1');
const pilotSection = pilotStart !== -1 ? app.slice(pilotStart) : '';

const lsWrites = pilotSection.match(/localStorage\.setItem\s*\([^)]+\)/g) || [];
const ssWrites = pilotSection.match(/sessionStorage\.setItem\s*\([^)]+\)/g) || [];
const idbRefs = pilotSection.match(/indexedDB/gi) || [];

console.log(`\n  Pilot localStorage writes found: ${lsWrites.length}`);
lsWrites.forEach(w => console.log('    - ' + w));

console.log(`  Pilot sessionStorage writes found: ${ssWrites.length}`);
ssWrites.forEach(w => console.log('    - ' + w));

console.log(`  Pilot IndexedDB references found: ${idbRefs.length}`);

if (lsWrites.length > 0 || ssWrites.length > 0 || idbRefs.length > 0) {
  allClean = false;
}

// Check Math.random for remote tokens
const tokenGenRegex = /function\s+.*[tT]oken.*\{[\s\S]*?Math\.random/g;
const hasRandomTokenGen = tokenGenRegex.test(pilotSection);
if (hasRandomTokenGen) {
  console.error('  ✗ FAIL: Found Math.random token generation');
  allClean = false;
} else {
  console.log('  ✓ PASS: No client-side Math.random token generation found');
}

console.log('\n═══════════════════════════════════════════════════════════════════════');
if (allClean) {
  console.log('✅ ZERO-STORAGE & STATIC PRIVACY AUDIT: 100% CLEAN');
} else {
  console.log('❌ ZERO-STORAGE & STATIC PRIVACY AUDIT: ISSUES DETECTED');
  process.exit(1);
}
console.log('═══════════════════════════════════════════════════════════════════════\n');
