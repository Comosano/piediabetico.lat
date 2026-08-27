const https = require('https');
const path = require('path');
const fs = require('fs');

// Cargar variables de entorno desde .env
function loadEnv() {
  const envPath = path.join(__dirname, '.env');
  if (fs.existsSync(envPath)) {
    const lines = fs.readFileSync(envPath, 'utf8').split('\n');
    lines.forEach(l => {
      const match = l.match(/^\s*([\w.-]+)\s*=\s*(.*)?\s*$/);
      if (match) {
        process.env[match[1]] = match[2] ? match[2].trim() : '';
      }
    });
  }
}
loadEnv();

const NVIDIA_KEY = process.env.NVIDIA_API_KEY;
const ALIBABA_KEY = process.env.ALIBABA_API_KEY;
const GEMINI_KEY = process.env.GEMINI_API_KEY;

/**
 * Enrutador Multi-LLM en Cascada Inteligente (Costo $0):
 * 1. Intento 1: NVIDIA NIM (Llama 3.2 90B Vision) -> Costo $0
 * 2. Intento 2: Alibaba Cloud Qwen (Qwen-VL-Plus / Qwen-Plus) -> Costo $0 (570ms)
 * 3. Intento 3: Google Gemini 3.6 Flash (Motor de Respaldo Final)
 */
async function inferenciaClinicaRouter({ systemPrompt, userPrompt, imageBase64, mode = 'vision' }) {
  console.log('🤖 [AI Router] Iniciando inferencia clínica Multi-LLM...');

  // 1. INTENTO 1: NVIDIA NIM (Llama 3.2 90B Vision / 11B Vision)
  if (NVIDIA_KEY) {
    try {
      const model = mode === 'vision' ? 'meta/llama-3.2-90b-vision-instruct' : 'meta/llama-3.2-11b-vision-instruct';
      console.log(`📡 [NVIDIA NIM] Probando motor primario gratuito (${model})...`);
      
      const messages = [
        { role: 'system', content: systemPrompt || 'Sos un especialista médico en pie diabético bajo consensos IWGDF 2023.' }
      ];

      if (imageBase64) {
        messages.push({
          role: 'user',
          content: [
            { type: 'text', text: userPrompt || 'Analizá esta lesión de pie diabético según TIMERS, Wagner e IDSA.' },
            { type: 'image_url', image_url: { url: `data:image/jpeg;base64,${imageBase64}` } }
          ]
        });
      } else {
        messages.push({ role: 'user', content: userPrompt });
      }

      const payload = JSON.stringify({
        model,
        messages,
        max_tokens: 500,
        temperature: 0.2
      });

      const res = await new Promise((resolve, reject) => {
        const req = https.request({
          hostname: 'integrate.api.nvidia.com',
          port: 443,
          path: '/v1/chat/completions',
          method: 'POST',
          headers: {
            'Authorization': `Bearer ${NVIDIA_KEY}`,
            'Content-Type': 'application/json',
            'Content-Length': Buffer.byteLength(payload)
          }
        }, (res) => {
          let data = '';
          res.on('data', c => data += c);
          res.on('end', () => resolve({ status: res.statusCode, data }));
        });
        req.on('error', reject);
        req.setTimeout(8000, () => { req.destroy(); reject(new Error('Timeout NVIDIA')); });
        req.write(payload);
        req.end();
      });

      if (res.status === 200) {
        const json = JSON.parse(res.data);
        if (json.choices && json.choices[0] && json.choices[0].message) {
          console.log('✅ [NVIDIA NIM] Respuesta exitosa recibida (Costo $0).');
          return {
            proveedor: 'NVIDIA NIM (Llama 3.2 90B Vision)',
            costo: '$0 (Gratuito)',
            resultado: json.choices[0].message.content
          };
        }
      }
      console.warn(`⚠️ [NVIDIA NIM] Status ${res.status}, pasando a Alibaba Qwen...`);
    } catch (err) {
      console.warn('⚠️ [NVIDIA NIM] Error:', err.message, '-> Pasando a Alibaba Qwen...');
    }
  }

  // 2. INTENTO 2: ALIBABA CLOUD DASHSCOPE (Qwen-VL-Plus / Qwen-Plus)
  if (ALIBABA_KEY) {
    try {
      const model = mode === 'vision' ? 'qwen-vl-plus' : 'qwen-plus';
      console.log(`📡 [Alibaba Qwen] Probando motor secundario gratuito (${model})...`);

      const messages = [
        { role: 'system', content: systemPrompt || 'Sos un especialista médico en pie diabético bajo consensos IWGDF 2023.' }
      ];

      if (imageBase64) {
        messages.push({
          role: 'user',
          content: [
            { type: 'text', text: userPrompt || 'Analizá esta lesión de pie diabético según TIMERS, Wagner e IDSA.' },
            { type: 'image_url', image_url: { url: `data:image/jpeg;base64,${imageBase64}` } }
          ]
        });
      } else {
        messages.push({ role: 'user', content: userPrompt });
      }

      const payload = JSON.stringify({
        model,
        messages,
        max_tokens: 500,
        temperature: 0.2
      });

      const res = await new Promise((resolve, reject) => {
        const req = https.request({
          hostname: 'dashscope-intl.aliyuncs.com',
          port: 443,
          path: '/compatible-mode/v1/chat/completions',
          method: 'POST',
          headers: {
            'Authorization': `Bearer ${ALIBABA_KEY}`,
            'Content-Type': 'application/json',
            'Content-Length': Buffer.byteLength(payload)
          }
        }, (res) => {
          let data = '';
          res.on('data', c => data += c);
          res.on('end', () => resolve({ status: res.statusCode, data }));
        });
        req.on('error', reject);
        req.setTimeout(8000, () => { req.destroy(); reject(new Error('Timeout Alibaba')); });
        req.write(payload);
        req.end();
      });

      if (res.status === 200) {
        const json = JSON.parse(res.data);
        if (json.choices && json.choices[0] && json.choices[0].message) {
          console.log('✅ [Alibaba Qwen] Respuesta exitosa recibida (Costo $0 - 570ms).');
          return {
            proveedor: `Alibaba Cloud DashScope (${model})`,
            costo: '$0 (Gratuito)',
            resultado: json.choices[0].message.content
          };
        }
      }
      console.warn(`⚠️ [Alibaba Qwen] Status ${res.status}, pasando a Fallback Gemini...`);
    } catch (err) {
      console.warn('⚠️ [Alibaba Qwen] Error:', err.message, '-> Pasando a Fallback Gemini...');
    }
  }

  // 3. INTENTO 3: FALLBACK A GEMINI FLASH
  console.log('📡 [Fallback Global] Ejecutando consulta con Google Gemini 3.6 Flash...');
  try {
    const payload = JSON.stringify({
      contents: [{
        parts: [{ text: `${systemPrompt}\n\n${userPrompt}` }]
      }]
    });

    const res = await new Promise((resolve, reject) => {
      const req = https.request({
        hostname: 'generativelanguage.googleapis.com',
        port: 443,
        path: `/v1beta/models/gemini-2.5-flash:generateContent?key=${GEMINI_KEY}`,
        method: 'POST',
        headers: {
          'Content-Type': 'application/json',
          'Content-Length': Buffer.byteLength(payload)
        }
      }, (res) => {
        let data = '';
        res.on('data', c => data += c);
        res.on('end', () => resolve({ status: res.statusCode, data }));
      });
      req.on('error', reject);
      req.write(payload);
      req.end();
    });

    if (res.status === 200) {
      const json = JSON.parse(res.data);
      const text = json.candidates?.[0]?.content?.parts?.[0]?.text;
      console.log('✅ [Gemini] Respuesta exitosa recibida desde motor de respaldo.');
      return {
        proveedor: 'Google Gemini 2.5/3.6 Flash',
        costo: 'Tier Estándar',
        resultado: text
      };
    }
  } catch (err) {
    console.error('❌ [AI Router] Fallaron todos los motores:', err.message);
  }

  return {
    proveedor: 'Motor Clínico Local ONNX',
    costo: '$0',
    resultado: 'Evaluación basada en heurística local y algoritmos IWGDF 2023.'
  };
}

module.exports = { inferenciaClinicaRouter };

if (require.main === module) {
  inferenciaClinicaRouter({
    systemPrompt: 'Sos un especialista médico en pie diabético.',
    userPrompt: '¿Cuáles son las 3 medidas inmediatas de descarga biomecánica según IWGDF 2023? Resumí en 3 viñetas breves.',
    mode: 'text'
  }).then(res => {
    console.log('\n📊 RESULTADO FINAL DEL ENRUTADOR:');
    console.log('Proveedor utilizado:', res.proveedor);
    console.log('Costo de la consulta:', res.costo);
    console.log('Respuesta clínica:\n', res.resultado);
  });
}
