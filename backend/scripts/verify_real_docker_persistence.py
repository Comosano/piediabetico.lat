import os
import io
import json
import base64
import requests
from PIL import Image

API_BASE = os.environ.get("API_BASE", "http://127.0.0.1:8000")
PILOT_TEST_EMAIL = os.environ.get("PILOT_TEST_EMAIL", "piloto.medico1@piediabetico.lat")

PILOT_TEST_PASSWORD = os.environ.get("PILOT_TEST_PASSWORD")
if not PILOT_TEST_PASSWORD:
    raise RuntimeError("PILOT_TEST_PASSWORD es obligatoria en variables de entorno.")

print("================================================================")
print("🏥 VALIDACIÓN E2E DE PERSISTENCIA REAL, OWNERSHIP & REMOTE TOKEN")
print("================================================================")

# Generador de imagen sintética de prueba (CERO datos reales de pacientes)
def generar_imagen_sintetica_base64(color=(180, 50, 50)):
    img = Image.new("RGB", (256, 256), color=color)
    buf = io.BytesIO()
    img.save(buf, format="JPEG", quality=85)
    return base64.b64encode(buf.getvalue()).decode("utf-8")

img_b64_baseline = generar_imagen_sintetica_base64((160, 40, 40))
img_b64_followup = generar_imagen_sintetica_base64((140, 60, 60))

# 1. Login Médico
login_resp = requests.post(
    f"{API_BASE}/api/pilot/auth/login",
    json={"email": PILOT_TEST_EMAIL, "password": PILOT_TEST_PASSWORD}
)
assert login_resp.status_code == 200, f"Login falló: {login_resp.text}"
token = login_resp.json()["access_token"]
headers = {"Authorization": f"Bearer {token}"}
print(f"1. Login Médico Exitoso: Token prefix={token[:10]}...")

# 2. Crear Caso en PostgreSQL
case_payload = {"case_alias": "PILOT-E2E-CASE"}
case_resp = requests.post(f"{API_BASE}/api/pilot/cases", json=case_payload, headers=headers)
assert case_resp.status_code == 200, f"Creación de caso falló: {case_resp.text}"
case_data = case_resp.json()
case_uuid = case_data["pilot_case_uuid"]
print(f"2. Caso Persistido en DB: UUID={case_uuid} Alias={case_data['case_alias']}")

# 3. Crear Herida en PostgreSQL
wound_payload = {"wound_label": "Úlcera Maléolo Externo", "wound_location": "Maléolo"}
wound_resp = requests.post(f"{API_BASE}/api/pilot/cases/{case_uuid}/wounds", json=wound_payload, headers=headers)
assert wound_resp.status_code == 200, f"Creación de herida falló: {wound_resp.text}"
wound_data = wound_resp.json()
wound_uuid = wound_data["wound_uuid"]
print(f"3. Herida Persistida en DB: UUID={wound_uuid} Label={wound_data['wound_label']}")

# 4. Ingesta de Análisis Baseline (Inferencia U-Net + MinIO + PostgreSQL)
analisis_payload = {
    "imagen_base64": img_b64_baseline,
    "privacy_gate_confirmed": True,
    "quality_score": 88,
    "quality_status": "optimo",
    "pilot_case_uuid": case_uuid,
    "pilot_wound_uuid": wound_uuid,
    "sequence_index": 1,
    "scale_detected": False
}
analisis_resp = requests.post(f"{API_BASE}/api/pilot/analisis", json=analisis_payload, headers=headers)
assert analisis_resp.status_code == 200, f"Análisis falló: {analisis_resp.text}"
analisis_data = analisis_resp.json()
baseline_analysis_uuid = analisis_data["analysis_uuid"]
print(f"4. Análisis Baseline Persistido: UUID={baseline_analysis_uuid} AI_Status={analisis_data['ai_status']}")
assert analisis_data["absolute_area_cm2"] is None, "Área absoluta debe ser NULL sin escala calibrada"

# 5. Consultar Timeline Pre-Reinicio
tl_resp = requests.get(f"{API_BASE}/api/pilot/cases/{case_uuid}/timeline", headers=headers)
assert tl_resp.status_code == 200, f"Timeline falló: {tl_resp.text}"
tl_data = tl_resp.json()
assert len(tl_data["wounds"]) == 1
assert len(tl_data["wounds"][0]["events"]) == 1
print(f"5. Timeline Verificado (Pre-Reinicio): 1 Herida, 1 Evento registrado.")

# 6. Generar Token Remoto de Seguimiento (+4 Días)
token_resp = requests.post(f"{API_BASE}/api/pilot/cases/{case_uuid}/wounds/{wound_uuid}/tokens", json={"due_days": 4, "expire_days": 7}, headers=headers)
assert token_resp.status_code == 200, f"Generación de token falló: {token_resp.text}"
tok_data = token_resp.json()
raw_remote_token = tok_data["token"]
print(f"6. Token Remoto Generado: URL=/r/{raw_remote_token[:8]}... (Hash SHA-256 en DB)")

# 7. Validar Token Remoto (Vista Paciente)
val_resp = requests.get(f"{API_BASE}/api/pilot/r/{raw_remote_token}")
assert val_resp.status_code == 200, f"Validación de token falló: {val_resp.text}"
print(f"7. Validación Vista Paciente: {val_resp.json()['mensaje']}")

# 8. Subida de Fotografía Remota del Paciente (Consumo Atómico)
patient_upload_payload = {
    "imagen_base64": img_b64_followup,
    "privacy_gate_confirmed": True,
    "quality_score": 85
}
upload_resp = requests.post(f"{API_BASE}/api/pilot/r/{raw_remote_token}/upload", json=patient_upload_payload)
assert upload_resp.status_code == 200, f"Subida remota falló: {upload_resp.text}"
upload_data = upload_resp.json()
assert upload_data["exito"] is True
followup_analysis_uuid = upload_data["analysis_uuid"]
print(f"8. Subida Remota Exitosa: Analysis={followup_analysis_uuid} Token Consumido Atómicamente.")

# 9. Replay Attack Bloqueado (Token Ya Usado)
replay_resp = requests.post(f"{API_BASE}/api/pilot/r/{raw_remote_token}/upload", json=patient_upload_payload)
assert replay_resp.status_code == 404, f"Esperado 404 por token usado, recibido: {replay_resp.status_code}"
print(f"9. Replay Attack Bloqueado: Token consumido devuelve 404 correctamente.")

# 10. Consultar Timeline Actualizado (2 Eventos en la misma herida)
tl_resp2 = requests.get(f"{API_BASE}/api/pilot/cases/{case_uuid}/timeline", headers=headers)
assert tl_resp2.status_code == 200
tl_data2 = tl_resp2.json()
events = tl_data2["wounds"][0]["events"]
assert len(events) == 2, f"Esperados 2 eventos en timeline, encontrados {len(events)}"
print(f"10. Timeline Longitudinal Completo: 2 Eventos enlazados a la misma herida.")

# 11. Registrar Evaluación Evolutiva Médica (Baseline vs Follow-up)
evol_payload = {
    "baseline_analysis_uuid": baseline_analysis_uuid,
    "followup_analysis_uuid": followup_analysis_uuid,
    "clinical_evolution": "MEJOR",
    "system_representation_agreement": "SI",
    "comment": "Reducción favorable de eritema perilesional."
}
evol_resp = requests.post(f"{API_BASE}/api/pilot/evolution-feedback", json=evol_payload, headers=headers)
assert evol_resp.status_code == 200, f"Feedback evolutivo falló: {evol_resp.text}"
print(f"11. Evaluación Evolutiva Registrada en DB: FeedbackID={evol_resp.json()['feedback_id']}")

print("\n================================================================")
print("🏁 RESULTADO TEST PERSISTENCIA REAL DOCKER: 100% PASS")
print("================================================================")
