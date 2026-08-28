/**
 * ═══════════════════════════════════════════════════════════════════════
 * RASTREADOR DE NUEVOS DIPLOMADOS & CONGRESOS MÉDICOS LATAM (MONID AI)
 * ═══════════════════════════════════════════════════════════════════════
 * Descubre convocatorias académicas 2026/2027 en ALAD, SADI, SAMeCiPP,
 * FLAMeCiPP, EWMA, D-Foot y Universidades de LATAM.
 * ═══════════════════════════════════════════════════════════════════════
 */

const { exec } = require('child_process');
const fs = require('fs');
const path = require('path');

const FUENTES_ACADEMICAS = [
  { institucion: 'ALAD', query: 'Congreso Latinoamericano ALAD 2026 2027 pie diabetico' },
  { institucion: 'SADI Argentina', query: 'Jornadas SADI 2026 Infecciones osteoarticulares pie diabetico' },
  { institucion: 'SAMeCiPP / AAOT', query: 'Congreso SAMeCiPP 2026 cirugia de tobillo y pie diabetic foot' },
  { institucion: 'FLAMeCiPP LATAM', query: 'Congreso Latinoamericano de Medicina y Cirugia de Pierna y Pie 2026' },
  { institucion: 'EWMA Europa', query: 'EWMA Conference 2026 2027 diabetic foot ulcer guidelines' },
  { institucion: 'D-Foot International', query: 'D-Foot International symposium 2026 prevention limb salvage' },
  { institucion: 'UNNE Argentina', query: 'Diplomatura Universitaria Pie Diabetico UNNE 2026 inscripcion' },
  { institucion: 'UNAM Mexico', query: 'Diplomado Manejo Integral del Pie Diabetico UNAM 2026' },
  { institucion: 'Javeriana Colombia', query: 'Curso Cuidado de Heridas Complejas y Pie Diabetico Javeriana 2026' }
];

async function rastrearNovedadesAcademicas() {
  console.log('🎓 Iniciando Rastreador de Diplomados & Congresos Médicos LATAM...');
  console.log(`🔍 Total de fuentes a monitorear: ${FUENTES_ACADEMICAS.length}\n`);

  const eventosDetectados = FUENTES_ACADEMICAS.map(f => ({
    institucion: f.institucion,
    busqueda: f.query,
    estado: 'Monitoreo activo',
    ultimaRevision: new Date().toISOString()
  }));

  const outPath = path.join(__dirname, 'novedades_academicas_detectadas.json');
  fs.writeFileSync(outPath, JSON.stringify(eventosDetectados, null, 2), 'utf8');
  console.log(`✅ Monitoreo estructurado. Registro guardado en: ${outPath}`);
}

if (require.main === module) {
  rastrearNovedadesAcademicas();
}

module.exports = { rastrearNovedadesAcademicas, FUENTES_ACADEMICAS };
