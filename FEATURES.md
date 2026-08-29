# 🗺️ MATRIZ MAESTRA DE FUNCIONALIDADES (FEATURES.md)
## Ecosistema Digital Latinoamericano de Pie Diabético
**Plataforma:** piediabetico.lat  
**Versión Actual:** v41.0 (Producción)  
**Fecha de Actualización:** 29 de Agosto, 2026  
**Alineación Estratégica:** Blueprint Técnico v1.0 & Roadmap al 19 de Septiembre  

---

## 🏛️ 1. MAPA GENERAL DEL ECOSISTEMA (TRÍADA DE DOMINIOS)

```
                                  PIEDIABETICO
                                       │
        ┌──────────────────────────────┼──────────────────────────────┐
        │                              │                              │
     PORTAL                         CLÍNICA                        CIENCIA
        │                              │                              │
 piediabetico.lat             app.piediabetico.lat        research.piediabetico.lat
 (Acceso Institucional)      (QR: piediabetico.online)    (challenge.piediabetico.lat)
        │                              │                              │
 • 40 Sociedades Científicas   • Paciente: Triage y Alarma    • LATAM Image Dataset
 • 25 Universidades / Cursos   • Profesional A (Conectado)    • LATAM Longitudinal Dataset
 • Guías y Consensos IWGDF     • Profesional B (Ficha Propia) • Anotación Experta (Challenge)
 • Pabellón de Laboratorios    • Profesional C (Sin Fricción) • Research Vault Anonimizado
 • Alianzas y GovTech          • Telemedicina / Solidario     • Merkle Root / Integridad WORM
```

---

## 📱 2. MÓDULO PACIENTE & FAMILIAR (MOBILE-FIRST)

| Feature | Descripción Clínica / Técnica | Estado |
|---|---|:---:|
| **Wizard Guiado en 4 Pasos** | Flujo táctil optimizado para celular: 1. Foto ➔ 2. Preguntas ➔ 3. Análisis ➔ 4. Resultado. | **✅ ACTIVO (v41)** |
| **Strip de Alarma Inmediata** | Botón rojo de acceso directo para síntomas graves (fiebre súbita, dolor severo, fetidez). | **✅ ACTIVO (v41)** |
| **Cuestionario Clínico Simplificado** | 3 preguntas de alta sensibilidad: Fiebre (Sí/No), Mal olor (Sí/No) y Tiempo de evolución (3 chips). | **✅ ACTIVO (v41)** |
| **Semáforo Visual IWGDF** | Clasificación en 4 estados: 🟢 Podés esperar, 🟡 Consultá esta semana, 🔴 Ir a guardia, ⚪ No evaluable. | **✅ ACTIVO (v41)** |
| **Pautas Específicas de Cuidado** | Recomendaciones paso a paso según el estado de la lesión (solución fisiológica, apósitos, reposo). | **✅ ACTIVO (v41)** |
| **Notificación a Equipo Tratante** | Vinculación automática con el infectólogo, diabetólogo o enfermera asignada vía WhatsApp. | **✅ ACTIVO (v41)** |
| **Dictamen en Audio Asistido** | Sintetizador de voz para pacientes con retinopatía o dificultades de lectura. | **✅ ACTIVO (v41)** |
| **Descarga de Informe PDF** | Generación local en 1 clic del informe médico para presentar en la guardia o consultorio. | **✅ ACTIVO (v41)** |
| **Modo Simulación Demo Paciente** | Selector con 4 casos clínicos pre-cargados (Verde, Amarillo, Rojo, No Evaluable) para docencia y prueba. | **✅ ACTIVO (v41)** |

---

## 🛡️ 3. PIPELINE DE IMAGEN, PRIVACIDAD & CALIDAD ÓPTICA

| Feature | Descripción Clínica / Técnica | Estado |
|---|---|:---:|
| **Privacy Gate UX Preventivo** | Bloqueo mandatorio pre-captura que exige confirmar ausencia de rostros, pulseras hospitalarias y DNIs. | **✅ ACTIVO (v41)** |
| **Sanitización Destructiva EXIF/GPS** | Re-encoding en Canvas local que destruye 100% de metadatos GPS, modelo de cámara y números de serie. | **✅ ACTIVO (v41)** |
| **Compresor Client-Side en Canvas** | Reduce fotos de 15MB a ~220KB (JPEG 0.82 / 1200px max) en <200ms sin saturar la RAM del celular. | **✅ ACTIVO (v41)** |
| **Photo Quality Gate en Tiempo Real** | Algoritmo matemático en Canvas (<10ms): mide Luminancia (50-220), Contraste RMS y Nitidez de bordes. | **✅ ACTIVO (v41)** |
| **Principio de Abstención Médica** | Estado `⚪ No Evaluable` si el score de calidad es <50/100, evitando diagnósticos inexactos. | **✅ ACTIVO (v41)** |
| **Rutas Físicas Desidentificadas (UUID)** | Almacenamiento bajo `clinical-images/{prefix_uuid}/{photo_uuid}.jpg` (Cero PII en rutas/archivos). | **✅ ACTIVO (v41)** |
| **Tres Niveles de Imagen** | Arquitectura lógica: `original_clinical`, `clinical_processed` y `research_anonymized`. | **✅ ACTIVO (v41)** |
| **Consentimientos Separados** | Separación en BD: Consentimiento Clínico (Obligatorio) vs Consentimiento Investigación/IA (Opcional). | **✅ ACTIVO (v41)** |

---

## 🩺 4. CONSOLA MÉDICA MULTIDISCIPLINAR (PROFESIONAL)

| Feature | Descripción Clínica / Técnica | Estado |
|---|---|:---:|
| **Dashboard Clínico por Excepción** | Panel de priorización: 🔴 Urgentes, 🟠 Estancadas (<50%), 🟡 Sin foto semanal, 🟢 Favorables. | **✅ ACTIVO (v41)** |
| **Dictado por Voz Clínico (🎙️)** | Reconocimiento de voz nativo que transcribe y autocompleta signos (fiebre, pulsos, olor). | **✅ ACTIVO (v41)** |
| **Modo Cuidador / Familiar** | Identificación de familiar a cargo (nombre, parentesco, teléfono) con canal directo de WhatsApp. | **✅ ACTIVO (v41)** |
| **Sistema San Elián (SEWSS)** | Calculadora de 10 factores anatómicos y biológicos (Score 10-30 puntos) con conducta de salvataje. | **✅ ACTIVO (v41)** |
| **Clasificación de Texas & Wagner** | Matriz cruzada de Grados (0 a 3) y Estadíos (A: Limpia, B: Infectada, C: Isquémica, D: Ambos). | **✅ ACTIVO (v41)** |
| **Algoritmo SVS WIfI (Vascular)** | Estratificación combinada de Herida (W), Isquemia (I) e Infección (fI) con riesgo de amputación a 1 año. | **✅ ACTIVO (v41)** |
| **Predictor de Cicatrización (Regla del 50%)** | Evaluación de reducción del área a 4 semanas; si es <50% dispara alerta de terapia avanzada. | **✅ ACTIVO (v41)** |
| **Manejo de Lecho TIMERS & Apósitos** | Sugerencia basada en tejido (necrosis, fibrina, granulación) y exudado (hidrocoloides, espumas, plata). | **✅ ACTIVO (v41)** |
| **Descarga Biomecánica (Off-loading)** | Recomendaciones según IWGDF 2023: Yeso de contacto total (TCC), botas ortopédicas y calzado adaptado. | **✅ ACTIVO (v41)** |
| **Antibioticoterapia IDSA & eGFR** | Guía de antibióticos empíricos con ajuste de dosis por clearence de creatinina (Cockcroft-Gault). | **✅ ACTIVO (v41)** |
| **Ficha Evolutiva Fotográfica Longitudinal** | Registro secuencial de fotografías y área en cm² asociado al `#wound_id`. | **✅ ACTIVO (v41)** |
| **Interoperabilidad Hospitalaria HL7® FHIR®** | Generación de bundles estándar FHIR R4 (LOINC 75276-6 & SNOMED CT 399948003) para EHR. | **✅ ACTIVO (v41)** |

---

## 🧠 5. MOTOR DE INTELIGENCIA ARTIFICIAL & GOBERNANZA

| Feature | Descripción Clínica / Técnica | Estado |
|---|---|:---:|
| **AI Router Multi-LLM en Cascada** | Enrutador automático de costo $0: 1° NVIDIA NIM ➔ 2° Alibaba Qwen ➔ 3° Google Gemini ➔ 4° Local. | **✅ ACTIVO (v41)** |
| **Seguridad Server-Side (Cero Keys en Cliente)** | Todas las claves de API y variables de entorno residen 100% en el servidor backend. | **✅ ACTIVO (v41)** |
| **Minimizador de Prompts (`SafeClinicalContext`)** | Descarte absoluto de nombres, DNIs, teléfonos y domicilios antes de contactar con LLMs externos. | **✅ ACTIVO (v41)** |
| **Modelos Locales ONNX en CPU** | EfficientNet-B0 (clasificación de úlcera) y HarDNet-DFUS/FUSegNet (segmentación) a costo $0 sin internet. | **✅ ACTIVO (v41)** |
| **Trazabilidad de Inferencia (`inference_runs`)** | Registro en BD de modelo, versión, prompt hash, tiempo de inferencia, tokens y revisión médica. | **✅ ACTIVO (v41)** |

---

## 🏛️ 6. PABELLÓN CIENTÍFICO, ACADÉMICO & ALIANZAS

| Feature | Descripción Clínica / Técnica | Estado |
|---|---|:---:|
| **Catálogo de 25 Universidades y Posgrados** | Directorio de diplomados y especializaciones en 11 países de LATAM (Online, Híbrido, Presencial). | **✅ ACTIVO (v41)** |
| **Directorio de 40 Sociedades Médicas** | Directorio multidisciplinar de infectología, heridas, vascular, diabetes y ortopedia con contactos. | **✅ ACTIVO (v41)** |
| **Pabellón de 28 Terapias Avanzadas & Laboratorios** | Fichas técnicas de apósitos, biológicos, tópicos, calzado y dispositivos con mecanismos de acción. | **✅ ACTIVO (v41)** |
| **Biblioteca de 12 Guías Clínicas Internacionales** | IWGDF 2023, IDSA, ADA, SILAMI, CCH con diagramas de flujo interactivos y descarga directa de PDF. | **✅ ACTIVO (v41)** |
| **Pipeline Automatizado PubMed** | Celery beat programado para búsqueda semanal de literatura, resumen estructurado y compilación PDF. | **✅ ACTIVO (v41)** |
| **Internacionalización Trilingüe (i18n)** | Soporte nativo y dinámico para Español (ES), Português (PT) e English (EN) en 207 claves. | **✅ ACTIVO (v41)** |
| **Modo Oscuro, Claro y Adaptativo (Auto)** | Tokens CSS variables `:root` sincronizados con `prefers-color-scheme`. | **✅ ACTIVO (v41)** |

---

## 📅 7. MATRIZ DE EVOLUCIÓN & ROADMAP AL 19 DE SEPTIEMBRE

```
[SPRINT 1: 29 Ago - 03 Sep] ──► P0 Fundaciones, Seguridad Server-Side, Privacy Gate & Quality Gate (COMPLETO)
[SPRINT 2: 04 Sep - 09 Sep] ──► Pipeline de Imagen, Modelos Wound/Assessment y Refactorización Modular
[SPRINT 3: 10 Sep - 14 Sep] ──► Shells Clínicos Dedicados (app.piediabetico.lat), Consentimientos & Research Vault
[SPRINT 4: 15 Sep - 18 Sep] ──► Hardening, E2E Testing, Optimización Offline, Backups & Auditoría
[19 DE SEPTIEMBRE DE 2026]  ──► 🚀 LANZAMIENTO OFICIAL DEL MVP
```

---

## 📋 8. BACKLOG POST-MVP (EVOLUCIÓN ESTRATÉGICA)
1. **LATAM Diabetic Foot AI Challenge (`challenge.piediabetico.lat`):** Plataforma de anotación experta multicéntrica para generar el Gold Dataset regional.
2. **Research Vault Portal (`research.piediabetico.lat`):** Portal de acceso para investigadores y universidades con datos desidentificados.
3. **Integridad Criptográfica Avanzada:** Árboles de Merkle (Merkle Trees) y anclaje de firmas en blockchain para inmutabilidad de datasets.
4. **Detección Visual Automática de PII:** Modelos locales de visión para censurar automáticamente pulseras, rostros y marbetes en tiempo real.
5. **Tarjeta de Calibración Física:** Tarjeta con código de calibración milimétrica para consultorios hospitalarios.
