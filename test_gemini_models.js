const apiKey = (process.env.GEMINI_API_KEY || 'GEMINI_API_KEY_PLACEHOLDER');

async function listAndTestModels() {
  console.log('--- Consultando modelos disponibles para esta API Key ---');
  try {
    const listRes = await fetch(`https://generativelanguage.googleapis.com/v1beta/models?key=${apiKey}`);
    const listData = await listRes.json();
    
    if (listData.models) {
      console.log('Modelos disponibles:');
      listData.models.forEach(m => {
        if (m.supportedGenerationMethods?.includes('generateContent')) {
          console.log(` - ${m.name}`);
        }
      });
    } else {
      console.log('Respuesta list:', listData);
    }

    // Probar gemini-3.6-flash
    const testModel = 'gemini-3.6-flash';
    console.log(`\nProbando inferencia con ${testModel}...`);
    const genRes = await fetch(`https://generativelanguage.googleapis.com/v1beta/models/${testModel}:generateContent?key=${apiKey}`, {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({
        contents: [{ parts: [{ text: "Hola, sos el asistente de piediabetico.lat. Confirmá en una frase que estás listo para analizar heridas de pie diabético." }] }]
      })
    });
    
    const genData = await genRes.json();
    if (genRes.ok) {
      console.log(`\n✓ ¡Éxito con ${testModel}!`);
      console.log('Respuesta:', genData.candidates?.[0]?.content?.parts?.[0]?.text);
    } else {
      console.log(`Error con ${testModel}:`, genData.error?.message || genData);
    }

  } catch (e) {
    console.error('Error:', e.message);
  }
}

listAndTestModels();
