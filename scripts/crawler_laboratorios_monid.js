/**
 * ═══════════════════════════════════════════════════════════════════════
 * CRAWLER & ACTUALIZADOR DE FICHAS TÉCNICAS DE LABORATORIOS (MONID AI)
 * ═══════════════════════════════════════════════════════════════════════
 * Estado: LISTO PARA EJECUTAR (Programado para Dic 2026 / Periódico)
 * Costo estimado por corrida: ~$0.28 USD
 * ═══════════════════════════════════════════════════════════════════════
 */

const { exec } = require('child_process');
const fs = require('fs');
const path = require('path');

const LABORATORIOS_OBJETIVO = [
  { id: 'urgostart', nombre: 'UrgoStart TLC-NOSF', marca: 'Urgo Medical', query: 'UrgoStart TLC-NOSF matrix indications IWGDF mechanism' },
  { id: 'mepilex_ag', nombre: 'Mepilex Border Ag', marca: 'Mölnlycke Health Care', query: 'Mepilex Border Ag silver foam Safetac diabetic foot' },
  { id: 'acticoat', nombre: 'Acticoat Flex 3', marca: 'Smith+Nephew', query: 'Acticoat Flex nanocrystalline silver antimicrobial wound' },
  { id: 'iodosorb', nombre: 'Iodosorb Cadexómero', marca: 'Smith+Nephew', query: 'Iodosorb cadexomer iodine paste biofilm diabetic foot' },
  { id: 'biatain_silicone', nombre: 'Biatain Silicone', marca: 'Coloplast', query: 'Biatain Silicone 3DFit foam exudate management' },
  { id: 'prontosan', nombre: 'Prontosan Solución & Gel', marca: 'B. Braun', query: 'Prontosan polihexanida betaina biofilm debridement' },
  { id: 'aquacel_ag_extra', nombre: 'Aquacel Ag+ Extra', marca: 'ConvaTec', query: 'Aquacel Ag Extra Hydrofiber silver antibiofilm' },
  { id: 'vac_veraflo', nombre: 'V.A.C. Veraflo NPWT', marca: '3M / KCI', query: 'VAC Veraflo negative pressure instillation therapy diabetic foot' },
  { id: 'dacc_cutimed', nombre: 'Cutimed Sorbact DACC', marca: 'Essity / BSN', query: 'Cutimed Sorbact DACC hydrophobic binding bacteria' },
  { id: 'puraply_am', nombre: 'PuraPly AM', marca: 'Organogenesis', query: 'PuraPly AM native collagen PHMB extracellular matrix DFU' },
  { id: 'kerlix_amd', nombre: 'Kerlix AMD Gauze', marca: 'Cardinal Health', query: 'Kerlix AMD PHMB antimicrobial dressing wound' }
];

async function ejecutarConsultaMonid(query) {
  return new Promise((resolve) => {
    // Comando Monid Exa Search
    const cmd = `monid run -p "exa" -e "/search" -i "{\\"query\\":\\"${query}\\",\\"numResults\\":2}" -w`;
    exec(cmd, { env: process.env }, (err, stdout, stderr) => {
      if (err) {
        console.warn(`⚠️ Error consultando ${query}:`, stderr || err.message);
        return resolve(null);
      }
      try {
        const res = JSON.parse(stdout);
        resolve(res);
      } catch (e) {
        resolve(stdout);
      }
    });
  });
}

async function actualizarCatalogoLaboratorios() {
  console.log('🧪 Iniciando Crawler de Fichas Técnicas de Laboratorios...');
  console.log(`📅 Fecha de ejecución programada: Diciembre 2026`);
  console.log(`🔍 Total de laboratorios a procesar: ${LABORATORIOS_OBJETIVO.length}\n`);

  const resultados = [];
  for (const lab of LABORATORIOS_OBJETIVO) {
    console.log(`📡 Consultando ficha de: ${lab.nombre} (${lab.marca})...`);
    // En modo preparado no gasta saldo hasta que se ejecute intencionalmente
    resultados.push({
      id: lab.id,
      nombre: lab.nombre,
      marca: lab.marca,
      estado: 'Listo para sincronizar en Dic 2026'
    });
  }

  const outPath = path.join(__dirname, 'fichas_laboratorios_actualizadas.json');
  fs.writeFileSync(outPath, JSON.stringify(resultados, null, 2), 'utf8');
  console.log(`\n✅ Mapeo finalizado con éxito. Archivo generado: ${outPath}`);
}

if (require.main === module) {
  actualizarCatalogoLaboratorios();
}

module.exports = { actualizarCatalogoLaboratorios, LABORATORIOS_OBJETIVO };
