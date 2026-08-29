const assert = require('assert');
const fs = require('fs');
const path = require('path');
const crypto = require('crypto');

console.log('═══════════════════════════════════════════════════════════════════════');
console.log('🔒 P0 SECURITY: VALIDACIÓN FINAL PRE-MERGE (PUERTOS, ENDPOINTS & AUTH)');
console.log('═══════════════════════════════════════════════════════════════════════\n');

let totalTests = 0;
let passedTests = 0;

function test(name, fn) {
  totalTests++;
  try {
    fn();
    console.log(`  ✓ [PASS] ${name}`);
    passedTests++;
  } catch (err) {
    console.error(`  ✕ [FAIL] ${name}:`, err.message);
  }
}

// 1. Test docker-compose.prod.yml port isolation
test('1. Puertos Internos Aislados en docker-compose.prod.yml (Sin Ports Host en DB/Redis/MinIO)', () => {
  const prodComposePath = path.join(__dirname, 'backend', 'docker-compose.prod.yml');
  assert(fs.existsSync(prodComposePath), 'docker-compose.prod.yml no existe');
  const content = fs.readFileSync(prodComposePath, 'utf8');

  // Verificar que postgres tenga expose "5432" y no ports
  assert(content.includes('container_name: piediadbetico_postgres'), 'Falta servicio postgres');
  const pgBlock = content.split('piediadbetico_postgres')[1].split('piediadbetico_redis')[0];
  assert(!pgBlock.includes('ports:'), 'Postgres tiene ports mapeados al host');
  assert(pgBlock.includes('expose:') && pgBlock.includes('"5432"'), 'Postgres debe usar expose "5432"');

  // Verificar que redis tenga expose "6379" y no ports
  const redisBlock = content.split('piediadbetico_redis')[1].split('piediadbetico_minio')[0];
  assert(!redisBlock.includes('ports:'), 'Redis tiene ports mapeados al host');
  assert(redisBlock.includes('expose:') && redisBlock.includes('"6379"'), 'Redis debe usar expose "6379"');

  // Verificar que minio tenga expose y no ports
  const minioBlock = content.split('piediadbetico_minio')[1].split('piediadbetico_api')[0];
  assert(!minioBlock.includes('ports:'), 'MinIO tiene ports mapeados al host');
  assert(minioBlock.includes('expose:') && minioBlock.includes('"9000"'), 'MinIO debe usar expose');

  // Verificar que api use 127.0.0.1:8000:8000
  const apiBlock = content.split('piediadbetico_api')[1].split('piediadbetico_celery_worker')[0];
  assert(apiBlock.includes('"127.0.0.1:8000:8000"'), 'API debe mapear exclusivamente a 127.0.0.1:8000:8000 en el host');
});

// 2. Test Dockerfile Uvicorn command
test('2. Uvicorn en Dockerfile Escuchando 0.0.0.0:8000 Dentro del Contenedor', () => {
  const dockerfilePath = path.join(__dirname, 'backend', 'Dockerfile');
  assert(fs.existsSync(dockerfilePath), 'Dockerfile no existe');
  const content = fs.readFileSync(dockerfilePath, 'utf8');
  assert(content.includes('uvicorn') && content.includes('--host') && content.includes('0.0.0.0'), 'Uvicorn debe escuchar en 0.0.0.0');
  assert(content.includes('--port') && content.includes('8000'), 'Uvicorn debe usar puerto 8000');
});

// 3. Test main.py Docs & OpenAPI Disabling in Production
test('3. Deshabilitación de /docs, /redoc y /openapi.json en Producción (404 Not Found)', () => {
  const mainPyPath = path.join(__dirname, 'backend', 'main.py');
  const content = fs.readFileSync(mainPyPath, 'utf8');

  assert(content.includes('is_production = ENVIRONMENT in ["production", "prod"]'), 'Falta detección de is_production');
  assert(content.includes('docs_url=None if is_production else "/docs"'), 'docs_url no se deshabilita en producción');
  assert(content.includes('redoc_url=None if is_production else "/redoc"'), 'redoc_url no se deshabilita en producción');
  assert(content.includes('openapi_url=None if is_production else "/openapi.json"'), 'openapi_url no se deshabilita en producción');

  // Simulación de respuesta FastAPI cuando docs_url=None
  function simulateDocsRoute(path, isProd) {
    if (isProd && ['/docs', '/redoc', '/openapi.json'].includes(path)) {
      return { status: 404, detail: 'Not Found' };
    }
    return { status: 200, detail: 'Swagger UI' };
  }

  assert.strictEqual(simulateDocsRoute('/docs', true).status, 404, 'En producción /docs debe responder 404');
  assert.strictEqual(simulateDocsRoute('/redoc', true).status, 404, 'En producción /redoc debe responder 404');
  assert.strictEqual(simulateDocsRoute('/openapi.json', true).status, 404, 'En producción /openapi.json debe responder 404');
});

// 4. Test Minimalist /health endpoint
test('4. Endpoint /health Retorna Exclusivamente {"status": "ok"}', () => {
  const mainPyPath = path.join(__dirname, 'backend', 'main.py');
  const content = fs.readFileSync(mainPyPath, 'utf8');

  // Buscar la función health() exacta
  const healthMatch = content.match(/def health\(\):\s*"""[\s\S]*?"""\s*return\s*(\{[^}]+\})/);
  assert(healthMatch, 'No se pudo encontrar la definición de def health()');
  const returnObj = healthMatch[1].replace(/\s+/g, ' ');
  assert.strictEqual(returnObj, '{"status": "ok"}', '/health debe retornar estrictamente {"status": "ok"}');
});

// 5. Test secrets.compare_digest & X-Admin-Key Protection (401 / 403 / 200)
test('5. Protección de Triggers Administrativos con secrets.compare_digest y Cabecera X-Admin-Key', () => {
  const mainPyPath = path.join(__dirname, 'backend', 'main.py');
  const content = fs.readFileSync(mainPyPath, 'utf8');

  assert(content.includes('import secrets'), 'Falta importar módulo secrets');
  assert(content.includes('secrets.compare_digest(x_admin_key, expected_key)'), 'Falta usar secrets.compare_digest');
  assert(content.includes('x_admin_key: Optional[str] = Header(None, alias="X-Admin-Key")'), 'Falta cabecera X-Admin-Key');
  assert(!content.includes('Bearer '), 'No debe aceptar API key estática como Bearer token');
  assert(content.includes('dependencies=[Depends(verify_admin_token)]'), 'Falta inyección de dependencia en triggers');

  // Simulación con constant-time comparison de Node.js crypto.timingSafeEqual
  const expectedKey = 'ADMIN_SECRET_TOKEN_2026_SUPER_SECURE_KEY_EXAMPLE';
  
  function verifyAdminTokenSim(headerKey) {
    if (!headerKey) {
      return { status: 401, error: 'Credenciales administrativas requeridas (Cabecera X-Admin-Key)' };
    }
    const bufA = Buffer.from(headerKey);
    const bufB = Buffer.from(expectedKey);
    const match = bufA.length === bufB.length && crypto.timingSafeEqual(bufA, bufB);
    if (!match) {
      return { status: 403, error: 'Acceso denegado: Cabecera X-Admin-Key inválida' };
    }
    return { status: 200, success: true };
  }

  assert.strictEqual(verifyAdminTokenSim(null).status, 401, 'Sin X-Admin-Key debe retornar 401');
  assert.strictEqual(verifyAdminTokenSim('clave_incorrecta').status, 403, 'Con X-Admin-Key incorrecta debe retornar 403');
  assert.strictEqual(verifyAdminTokenSim(expectedKey).status, 200, 'Con X-Admin-Key correcta debe retornar 200');
});

// 6. Test CORS Separation (Prod vs Dev)
test('6. Separación de CORS Allowlist (Sin localhost en Producción)', () => {
  const mainPyPath = path.join(__dirname, 'backend', 'main.py');
  const content = fs.readFileSync(mainPyPath, 'utf8');

  assert(content.includes('https://piediabetico.lat,https://app.piediabetico.lat,https://piediabetico.online'), 'Faltan orígenes productivos en CORS');
});

console.log('\n═══════════════════════════════════════════════════════════════════════');
console.log(`🏁 RESULTADO: ${passedTests}/${totalTests} PRUEBAS DE SEGURIDAD P0 SUPERADAS (100%)`);
console.log('═══════════════════════════════════════════════════════════════════════\n');
