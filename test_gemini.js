const apiKey = (process.env.GEMINI_API_KEY || 'GEMINI_API_KEY_PLACEHOLDER');

async function testGemini() {
  console.log('--- Probando conexión con Google Gemini API ---');
  
  const models = ['gemini-2.5-flash', 'gemini-2.0-flash', 'gemini-1.5-flash'];
  
  for (const model of models) {
    try {
      console.log(`Probando modelo: ${model}...`);
      const url = `https://generativelanguage.googleapis.com/v1beta/models/${model}:generateContent?key=${apiKey}`;
      
      const payload = {
        contents: [
          {
            parts: [
              { text: "Respondé en 1 oración: Sos un asistente de salud de piediabetico.lat. ¿Cuál es tu función?" }
            ]
          }
        ]
      };

      const res = await fetch(url, {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify(payload)
      });

      const data = await res.json();
      
      if (res.ok) {
        console.log(`✓ Modelo ${model} funcionando perfectamente!`);
        console.log('Respuesta:', data.candidates?.[0]?.content?.parts?.[0]?.text);
        return;
      } else {
        console.log(`Error con ${model}:`, data.error?.message || data);
      }
    } catch (e) {
      console.log(`Excepción con ${model}:`, e.message);
    }
  }
}

testGemini();
