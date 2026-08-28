/**
 * ═══════════════════════════════════════════════════════════════════════
 * PUBLICADOR AUTOMÁTICO DE CONTENIDO & DIFUSIÓN (COMPOSIO.DEV)
 * ═══════════════════════════════════════════════════════════════════════
 * Estado: LISTO PARA VINCULAR CUENTAS (Instagram / LinkedIn / Gmail)
 * Permite programar y publicar infografías clínicas, prevención IWGDF
 * y alertas sanitarias en redes oficiales de piediabetico.lat a costo $0.
 * ═══════════════════════════════════════════════════════════════════════
 */

const fs = require('fs');
const path = require('path');

const PLANTILLAS_CONTENIDO_EDUCATIVO = [
  {
    id: "post_iwgdf_50rule",
    red: "LinkedIn",
    titulo: "La Regla de Oro del IWGDF: 50% de Cicatrización a 4 Semanas",
    copy: `¿Sabías que si una úlcera de pie diabético no reduce su área al menos un 50% tras 4 semanas de buen tratamiento, la probabilidad de no cicatrizar a 12 semanas supera el 68%?

En piediabetico.lat integramos el calculador de tasa de cicatrización bajo directrices IWGDF 2023 para alertar tempranamente la necesidad de terapias avanzadas (apósitos con matriz TLC-NOSF, terapia de presión negativa o revascularización).

👉 Probá la Estación Clínica Multidisciplinar gratuita en: https://piediabetico.lat

#PieDiabetico #IWGDF #MedicinaBasadaEnEvidencia #SaludDigital #HeridasComplejas`,
    horarioSugerido: "Martes 09:30 hs"
  },
  {
    id: "post_paciente_espejo",
    red: "Instagram",
    titulo: "Tu Rutina de 30 Segundos: Cómo salvar tus pies con un espejo",
    copy: `🦶 ¿Tenés diabetes? La pérdida de sensibilidad (neuropatía) puede hacer que una piedrita o ampolla pase desapercibida.

Revisá tus talones y la planta de tus pies todos los días usando un espejo de mano o pidiéndole ayuda a un familiar.

Si notás enrojecimiento, calor o una mancha oscura, consultá inmediatamente a tu equipo de salud.

🎧 Escuchá nuestras audioguías gratuitas de prevención en: https://piediabetico.lat

#DiabetesLATAM #PieDiabetico #Prevencion #SaludLATAM #CuidadoDePies`,
    horarioSugerido: "Jueves 19:30 hs"
  },
  {
    id: "post_antibioticos_sadi",
    red: "LinkedIn",
    titulo: "Infección en Pie Diabético: No todo eritema requiere vancomicina",
    copy: `El uso indiscriminado de antibióticos de amplio espectro en úlceras superficiales sin signos de celulitis o infección profunda genera resistencia bacteriana sin acelerar la cicatrización.

El consenso IDSA / IWGDF 2023 recomienda cultivo por punción o legrado de tejido profundo (evitando hisopados superficiales) y antibioterapia dirigida.

Consultá las guías completas en https://piediabetico.lat

#Infectologia #SADI #AntimicrobialStewardship #PieDiabetico`,
    horarioSugerido: "Lunes 14:00 hs"
  }
];

async function generarPlanDePublicacion() {
  console.log('🤖 Módulo de Difusión & Redes Sociales (Composio)...');
  console.log('📋 Estado actual: Cuentas pendientes de vinculación por el usuario.');
  console.log(`📝 Total de piezas clínicas listas para programar: ${PLANTILLAS_CONTENIDO_EDUCATIVO.length}\n`);

  PLANTILLAS_CONTENIDO_EDUCATIVO.forEach((p, i) => {
    console.log(`  [${i+1}] [${p.red}] ${p.titulo} (${p.horarioSugerido})`);
  });

  const outPath = path.join(__dirname, 'cola_publicaciones_redes.json');
  fs.writeFileSync(outPath, JSON.stringify(PLANTILLAS_CONTENIDO_EDUCATIVO, null, 2), 'utf8');
  console.log(`\n✅ Cola de contenido guardada en: ${outPath}`);
  console.log('ℹ️ Para activar el despacho automático, vinculá tus cuentas de LinkedIn/Instagram en app.composio.dev.');
}

if (require.main === module) {
  generarPlanDePublicacion();
}

module.exports = { generarPlanDePublicacion, PLANTILLAS_CONTENIDO_EDUCATIVO };
