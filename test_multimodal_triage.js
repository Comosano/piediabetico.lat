const apiKey = (process.env.GEMINI_API_KEY || 'GEMINI_API_KEY_PLACEHOLDER');
const model = 'gemini-3.6-flash';

// Imagen de prueba sintética (1x1 PNG transparente o muestra)
const sampleImageBase64 = 'iVBORw0KGgoAAAANSUhEUgAAAAEAAAABCAYAAAAfFcSJAAAADUlEQVR42mP8z8BQDwAEhQGAhKmMIQAAAABJRU5ErkJggg==';

async function testTriageProfiles() {
  console.log('═══════════════════════════════════════════════════════════════════════');
  console.log('🧪 PRUEBA MULTIMODAL DE TRIAGE CLÍNICO — piediabetico.lat');
  console.log(`Modelo: ${model} | Motor: Google Gemini`);
  console.log('═══════════════════════════════════════════════════════════════════════\n');

  const perfiles = [
    {
      id: 'paciente',
      system: `Sos un asistente de salud especializado en el cuidado del pie diabético. Hablás con una persona que tiene diabetes. Usá lenguaje simple, sin términos médicos.
ESTRUCTURA:
1. Lo que ves (1-2 oraciones)
2. Nivel de urgencia: UNA de estas opciones con su ícono exacto:
   🟢 PODÉS ESPERAR — Atendelo en tu próxima consulta
   🟡 CONSULTÁ ESTA SEMANA — Llamá a tu médico en 24 a 72hs
   🔴 CONSULTÁ HOY — Buscá atención médica hoy mismo / guardia
3. Qué hacer ahora (2-3 pasos simples)
4. Señal de alarma urgente`,
      userPrompt: 'Analizá esta foto. El paciente reporta: Fiebre actual: NO, Mal olor: SÍ, Dolor: NO, Tiempo de evolución: 2 semanas.'
    },
    {
      id: 'podologo_enfermero',
      system: `Sos un asistente clínico especializado en pie diabético para podólogos y enfermeros.
ESTRUCTURA:
**EVALUACIÓN DEL LECHO DE LA HERIDA** (tejido, bordes, exudado)
**SISTEMÁTICA TIMERS** (T, I, M, E, R, S)
**SUGERENCIA DE CONDUCTA & APÓSITO**`,
      userPrompt: 'Analizá esta lesión ulcerada en antepié plantar. Tiempo de evolución: 2 semanas, exudado moderado fétido, pulsos presentes, monofilamento anormal.'
    }
  ];

  for (const p of perfiles) {
    console.log(`\n🩺 ─────────────────── [PERFIL: ${p.id.toUpperCase()}] ───────────────────`);
    const startTime = Date.now();

    const payload = {
      systemInstruction: { parts: [{ text: p.system }] },
      contents: [
        {
          parts: [
            { inlineData: { mimeType: 'image/png', data: sampleImageBase64 } },
            { text: p.userPrompt }
          ]
        }
      ],
      generationConfig: {
        maxOutputTokens: 600,
        temperature: 0.2
      }
    };

    try {
      const res = await fetch(`https://generativelanguage.googleapis.com/v1beta/models/${model}:generateContent?key=${apiKey}`, {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify(payload)
      });

      const data = await res.json();
      const elapsed = Date.now() - startTime;

      if (res.ok) {
        const text = data.candidates?.[0]?.content?.parts?.[0]?.text;
        console.log(`⏱️ Latencia: ${elapsed} ms\n`);
        console.log(text);
      } else {
        console.log('Error API:', data.error?.message);
      }
    } catch (e) {
      console.log('Error de red:', e.message);
    }
  }
}

testTriageProfiles();
