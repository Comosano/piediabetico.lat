import os
import json
import hashlib
import requests
import redis

API_BASE = os.environ.get("API_BASE", "http://127.0.0.1:8000")
REDIS_URL = os.environ.get("REDIS_URL", "redis://redis:6379/0")
PILOT_TEST_EMAIL = os.environ.get("PILOT_TEST_EMAIL", "piloto.medico1@piediabetico.lat")

# Contraseña obligatoria desde entorno (NUNCA hardcodeada)
PILOT_TEST_PASSWORD = os.environ.get("PILOT_TEST_PASSWORD")
if not PILOT_TEST_PASSWORD:
    raise RuntimeError(
        "PILOT_TEST_PASSWORD es obligatoria en variables de entorno para ejecutar la prueba de autenticación real. "
        "Ejemplo: PILOT_TEST_PASSWORD='...' python scripts/verify_real_docker_auth.py"
    )

print("================================================================")
print("🔐 VALIDACIÓN DE RUNTIME AUTH REAL (POSTGRESQL + REDIS)")
print("================================================================")

# 1. Real Login
login_payload = {
    "email": PILOT_TEST_EMAIL.lower().strip(),
    "password": PILOT_TEST_PASSWORD
}

resp = requests.post(f"{API_BASE}/api/pilot/auth/login", json=login_payload)
print(f"1. Login Status: {resp.status_code}")
assert resp.status_code == 200, f"Login falló: {resp.text}"

data = resp.json()
token = data["access_token"]
user_info = data["user"]
print(f"✓ Login Exitoso: Usuario={user_info['email']} Rol={user_info['role']} Pilot={user_info['pilot_enabled']}")
print(f"✓ Token Emitido: Prefijo={token[:10]}... (Opaque URL-Safe 32 bytes)")

# 2. Redis Inspection
r = redis.Redis.from_url(REDIS_URL, decode_responses=True)
token_hash = hashlib.sha256(token.strip().encode("utf-8")).hexdigest()
redis_key = f"pilot_session:{token_hash}"

val = r.get(redis_key)
print(f"\n2. Redis Key Evaluada: pilot_session:<sha256_hash_64_chars>")
print(f"✓ Key Existe en Redis: {val is not None}")

session_dict = json.loads(val)
print(f"✓ Session Metadata en Redis: user_id={session_dict.get('user_id')} created_at={session_dict.get('created_at')}")
assert session_dict["user_id"] == user_info["id"]
assert "ip" not in session_dict, "Data minimization: IP no debe almacenarse en Redis"
assert "ua" not in session_dict, "Data minimization: UA no debe almacenarse en Redis"

# 3. Verify Raw Bearer Token is NOT stored
for k in r.keys("pilot_session:*"):
    assert k != token, "El token en texto plano no debe ser una clave en Redis"
    v = r.get(k)
    assert token not in v, "El token en texto plano no debe estar en el valor de Redis"
print("✓ CERO Fuga de Token: Bearer token en texto plano NUNCA almacenado en Redis.")

# 4. Authenticated Request to /api/pilot/ai-readiness
headers = {"Authorization": f"Bearer {token}"}
resp_readiness = requests.get(f"{API_BASE}/api/pilot/ai-readiness", headers=headers)
print(f"\n3. Request Protegido (Con Token): Status={resp_readiness.status_code}")
assert resp_readiness.status_code == 200, f"Readiness falló: {resp_readiness.text}"
print(f"✓ AI Readiness Data: {json.dumps(resp_readiness.json(), indent=2)}")

# 5. Unauthenticated Request
resp_unauth = requests.get(f"{API_BASE}/api/pilot/ai-readiness")
print(f"\n4. Request No Autenticado (Sin Token): Status={resp_unauth.status_code}")
assert resp_unauth.status_code == 401, f"Esperado 401, recibido {resp_unauth.status_code}"
print("✓ Fail-Closed Verificado: 401 Unauthorized sin token.")

# 6. Tampered Token Request
resp_tampered = requests.get(f"{API_BASE}/api/pilot/ai-readiness", headers={"Authorization": "Bearer pd_sess_tampered_token_xyz_12345"})
print(f"\n5. Request con Token Manipulado: Status={resp_tampered.status_code}")
assert resp_tampered.status_code == 401
print("✓ Fail-Closed Verificado: 401 Unauthorized para token inválido.")

print("\n================================================================")
print("🏁 RESULTADO RUNTIME AUTH REAL: 100% PASS")
print("================================================================")
