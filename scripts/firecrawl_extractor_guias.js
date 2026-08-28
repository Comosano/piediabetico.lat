/**
 * ═══════════════════════════════════════════════════════════════════════
 * EXTRACTOR DE GUÍAS MÉDICAS & DIPLOMADOS CON FIRECRAWL API
 * ═══════════════════════════════════════════════════════════════════════
 * Convierte páginas web médicas complejas en Markdown limpio para LLMs.
 * Plan: 1.000 páginas/mes gratis ($0 costo).
 * ═══════════════════════════════════════════════════════════════════════
 */

const https = require('https');
const fs = require('fs');
const path = require('path');

const FIRECRAWL_API_KEY = process.env.FIRECRAWL_API_KEY || 'fc-92daed27af4948f29d40a1a31f1c879a';

const FUENTES_PRIORITARIAS = [
  {
    id: 'iwgdf_2023',
    titulo: 'Consenso Internacional IWGDF 2023',
    url: 'https://iwgdfguidelines.org/guidelines/guidelines-2023/',
    categoria: 'Guías Clínicas'
  },
  {
    id: 'sadi_infecciones',
    titulo: 'Guías SADI Infecciones en Pie Diabético',
    url: 'https://www.sadi.org.ar',
    categoria: 'Sociedades Científicas'
  },
  {
    id: 'ewma_wound',
    titulo: 'EWMA European Wound Management Association',
    url: 'https://ewma.org',
    categoria: 'Cicatrización'
  }
];

async function scrapearConFirecrawl(url) {
  return new Promise((resolve, reject) => {
    const data = JSON.stringify({
      url: url,
      formats: ['markdown']
    });

    const options = {
      hostname: 'api.firecrawl.dev',
      port: 443,
      path: '/v1/scrape',
      method: 'POST',
      headers: {
        'Content-Type': 'application/json',
        'Authorization': `Bearer ${FIRECRAWL_API_KEY}`,
        'Content-Length': Buffer.byteLength(data)
      }
    };

    const req = https.request(options, (res) => {
      let body = '';
      res.on('data', (d) => { body += d; });
      res.on('end', () => {
        try {
          const parsed = JSON.parse(body);
          if (parsed.success && parsed.data) {
            resolve(parsed.data.markdown);
          } else {
            reject(new Error(parsed.error || `Error HTTP ${res.statusCode}: ${body}`));
          }
        } catch (e) {
          reject(e);
        }
      });
    });

    req.on('error', reject);
    req.write(data);
    req.end();
  });
}

async function procesarFuentesMedicas() {
  console.log('🔥 Iniciando Extracción Médica con Firecrawl API...');
  console.log(`🔑 Clave activa: ${FIRECRAWL_API_KEY.slice(0, 8)}...`);

  const cacheDir = path.join(__dirname, '..', 'data', 'firecrawl_cache');
  if (!fs.existsSync(cacheDir)) {
    fs.mkdirSync(cacheDir, { recursive: true });
  }

  for (const fuente of FUENTES_PRIORITARIAS) {
    console.log(`\n📄 Extrayendo: ${fuente.titulo} (${fuente.url})...`);
    try {
      const markdown = await scrapearConFirecrawl(fuente.url);
      const outPath = path.join(cacheDir, `${fuente.id}.md`);
      fs.writeFileSync(outPath, markdown, 'utf8');
      console.log(`  ✓ Guardado en Markdown limpio: ${outPath} (${markdown.length} bytes)`);
    } catch (err) {
      console.warn(`  ⚠️ Error procesando ${fuente.titulo}:`, err.message);
    }
  }

  console.log('\n✅ Extracción con Firecrawl completada exitosamente.');
}

if (require.main === module) {
  procesarFuentesMedicas();
}

module.exports = { scrapearConFirecrawl, procesarFuentesMedicas, FUENTES_PRIORITARIAS };
