/**
 * ═══════════════════════════════════════════════════════════════════════
 * CLIENTE OFICIAL DE EVIDENCE MD (RAZONAMIENTO CLÍNICO CON CITAS PEER-REVIEWED)
 * ═══════════════════════════════════════════════════════════════════════
 * API Médica anti-alucinaciones compatible con OpenAI.
 * Modelo: evidencemd-fast (4 créditos = $0.20) / evidencemd-deep (5 créditos = $0.25)
 * ═══════════════════════════════════════════════════════════════════════
 */

const https = require('https');

const EVIDENCEMD_API_KEY = process.env.EVIDENCEMD_API_KEY || 'emd_dd05c1_959ff55d48ad09563c85e4bd243260669853afc915329ddcfdfbdf0302fbd3ea';

async function consultarEvidenceMD(preguntaClinica, modelo = 'evidencemd-fast') {
  return new Promise((resolve, reject) => {
    const data = JSON.stringify({
      model: modelo,
      messages: [
        {
          role: 'system',
          content: 'Sos el Asistente Clínico Experto de piediabetico.lat. Respondé en español basándote estrictamente en consensos IWGDF 2023, IDSA, SVS WIfI, ADA y guías latinoamericanas con citas explícitas.'
        },
        {
          role: 'user',
          content: preguntaClinica
        }
      ],
      stream: false
    });

    const options = {
      hostname: 'evidencemd.ai',
      port: 443,
      path: '/api/v1/chat/completions',
      method: 'POST',
      headers: {
        'Content-Type': 'application/json',
        'x-api-key': EVIDENCEMD_API_KEY,
        'Content-Length': Buffer.byteLength(data)
      }
    };

    const req = https.request(options, (res) => {
      let body = '';
      res.on('data', (d) => { body += d; });
      res.on('end', () => {
        try {
          const json = JSON.parse(body);
          if (json.choices && json.choices.length > 0) {
            resolve({
              exito: true,
              contenido: json.choices[0].message.content,
              modelo: json.model,
              id: json.id
            });
          } else {
            reject(new Error(json.error?.message || `Error en respuesta: ${body}`));
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

if (require.main === module) {
  const preguntaPrueba = '¿Cuáles son las indicaciones de biopsia ósea versus hisopado en sospecha de osteomielitis en pie diabético según IDSA 2023?';
  console.log(`🔬 Consultando EvidenceMD (${preguntaPrueba})...`);
  consultarEvidenceMD(preguntaPrueba)
    .then(res => {
      console.log('\n✅ Respuesta con Evidencia Peer-Reviewed Verificada:');
      console.log(res.contenido);
    })
    .catch(err => {
      console.error('❌ Error consultando EvidenceMD:', err.message);
    });
}

module.exports = { consultarEvidenceMD };
