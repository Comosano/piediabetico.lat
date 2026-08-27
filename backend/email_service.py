"""
╔══════════════════════════════════════════════════════════════════════╗
║  EMAIL_SERVICE.PY — SERVICIO DE NEWSLETTER & CONTACTO (RESEND / SMTP)║
║  piediabetico.lat — Salud Digital LATAM                              ║
╚══════════════════════════════════════════════════════════════════════╝
"""

import os
import json
import logging
import urllib.request
import urllib.error
from datetime import datetime
from typing import Dict, Any, Optional, List

logger = logging.getLogger("email_service")
logger.setLevel(logging.INFO)

RESEND_API_KEY = os.getenv("RESEND_API_KEY", "")
FROM_EMAIL = os.getenv("FROM_EMAIL", "piediabetico.lat <newsletter@piediabetico.lat>")
SUBSCRIPTORES_FILE = os.path.join(os.path.dirname(os.path.abspath(__file__)), "suscriptores_newsletter.json")
CONSULTAS_FILE = os.path.join(os.path.dirname(os.path.abspath(__file__)), "consultas_contacto.json")

# ═══════════════════════════════════════════════════════════════════════
# PLANTILLAS HTML DE CORREO ELECTRÓNICO (RESPONSIVE & MEDICAL GRADE)
# ═══════════════════════════════════════════════════════════════════════

def get_template_bienvenida_medico(email: str) -> str:
    return f"""<!DOCTYPE html>
<html lang="es">
<head>
  <meta charset="utf-8">
  <title>Bienvenido a piediabetico.lat</title>
  <style>
    body {{ font-family: -apple-system, BlinkMacSystemFont, 'Segoe UI', Roboto, Helvetica, Arial, sans-serif; background-color: #F8FAFC; margin: 0; padding: 0; color: #1E293B; }}
    .container {{ max-width: 600px; margin: 20px auto; background-color: #FFFFFF; border-radius: 16px; overflow: hidden; border: 1px solid #E2E8F0; box-shadow: 0 4px 12px rgba(0,0,0,0.05); }}
    .header {{ background: linear-gradient(135deg, #0F172A, #0D9488); padding: 32px 24px; text-align: center; color: #FFFFFF; }}
    .logo-badge {{ display: inline-block; background: rgba(255,255,255,0.15); border: 1px solid rgba(255,255,255,0.25); border-radius: 12px; padding: 8px 16px; font-weight: 800; font-size: 18px; margin-bottom: 8px; }}
    .header h1 {{ margin: 0; font-size: 24px; font-weight: 900; }}
    .header p {{ margin: 6px 0 0 0; font-size: 13px; color: #CCFBF1; }}
    .body {{ padding: 32px 28px; line-height: 1.6; font-size: 14px; color: #334155; }}
    .card {{ background: #F0FDF4; border: 1px solid #BBF7D0; border-radius: 12px; padding: 18px; margin: 20px 0; }}
    .card h3 {{ margin: 0 0 8px 0; font-size: 15px; color: #166534; }}
    .btn {{ display: inline-block; background-color: #0D9488; color: #FFFFFF !important; text-decoration: none; padding: 12px 24px; border-radius: 10px; font-weight: bold; font-size: 14px; margin-top: 15px; text-align: center; }}
    .footer {{ background-color: #F1F5F9; padding: 20px; text-align: center; font-size: 11px; color: #64748B; border-top: 1px solid #E2E8F0; }}
    .footer a {{ color: #0D9488; text-decoration: underline; }}
  </style>
</head>
<body>
  <div class="container">
    <div class="header">
      <div class="logo-badge">🦶 piediabetico.lat</div>
      <h1>¡Bienvenido a la Red Científica!</h1>
      <p>Boletín Oficial de Consensos Clínicos & Algoritmos de Triage</p>
    </div>
    <div class="body">
      <p>Estimado/a colega,</p>
      <p>Hemos confirmado tu suscripción al boletín mensual de <strong>piediabetico.lat</strong> para la casilla <code>{email}</code>.</p>
      
      <div class="card">
        <h3>📚 ¿Qué recibirás mensualmente?</h3>
        <ul>
          <li><strong>Consensos IWGDF 2023 & ALAD</strong> traducidos y resumidos en esquemas prácticos.</li>
          <li><strong>Tablas de dosificación antibiótica</strong> con ajuste por clearance Cockcroft-Gault (SADI/IDSA).</li>
          <li><strong>Casos clínicos del mes</strong> con mapas de calor Grad-CAM y segmentación de tejidos en cm².</li>
          <li><strong>Convocatorias a congresos</strong> (HENDOLAT, AMEXIPIED, CLAD) y fechas de envío de abstracts.</li>
        </ul>
      </div>

      <p>Podés acceder en cualquier momento a nuestra biblioteca digital con las 12 Guías Clínicas Oficiales y utilizar las calculadoras de San Elián y SVS WIfI de forma gratuita:</p>
      
      <div style="text-align: center;">
        <a href="https://piediabetico.lat" class="btn">Acceder a la Estación Clínica</a>
      </div>
    </div>
    <div class="footer">
      <p>© 2026 piediabetico.lat · Salud Digital & Educación Médica Continua LATAM</p>
      <p>Cumplimiento estricto Ley 25.326 / LGPD. Para darte de baja con 1 clic, hacé <a href="https://piediabetico.lat?unsubscribe={email}">clic aquí</a>.</p>
    </div>
  </div>
</body>
</html>"""


def get_template_bienvenida_paciente(email: str) -> str:
    return f"""<!DOCTYPE html>
<html lang="es">
<head>
  <meta charset="utf-8">
  <title>Cuidado de tus Pies · piediabetico.lat</title>
  <style>
    body {{ font-family: -apple-system, BlinkMacSystemFont, 'Segoe UI', Roboto, Helvetica, Arial, sans-serif; background-color: #F8FAFC; margin: 0; padding: 0; color: #1E293B; }}
    .container {{ max-width: 600px; margin: 20px auto; background-color: #FFFFFF; border-radius: 16px; overflow: hidden; border: 1px solid #E2E8F0; box-shadow: 0 4px 12px rgba(0,0,0,0.05); }}
    .header {{ background: linear-gradient(135deg, #059669, #0D9488); padding: 32px 24px; text-align: center; color: #FFFFFF; }}
    .logo-badge {{ display: inline-block; background: rgba(255,255,255,0.2); border: 1px solid rgba(255,255,255,0.3); border-radius: 12px; padding: 8px 16px; font-weight: 800; font-size: 18px; margin-bottom: 8px; }}
    .header h1 {{ margin: 0; font-size: 22px; font-weight: 900; }}
    .body {{ padding: 32px 28px; line-height: 1.6; font-size: 14px; color: #334155; }}
    .tip {{ background: #ECFDF5; border-left: 4px solid #10B981; padding: 14px 18px; margin: 16px 0; border-radius: 0 10px 10px 0; }}
    .btn {{ display: inline-block; background-color: #059669; color: #FFFFFF !important; text-decoration: none; padding: 12px 24px; border-radius: 10px; font-weight: bold; font-size: 14px; margin-top: 15px; text-align: center; }}
    .footer {{ background-color: #F1F5F9; padding: 20px; text-align: center; font-size: 11px; color: #64748B; border-top: 1px solid #E2E8F0; }}
    .footer a {{ color: #059669; text-decoration: underline; }}
  </style>
</head>
<body>
  <div class="container">
    <div class="header">
      <div class="logo-badge">🦶 piediabetico.lat</div>
      <h1>¡Te damos la bienvenida!</h1>
      <p>Consejos prácticos para cuidar la salud de tus pies</p>
    </div>
    <div class="body">
      <p>Hola,</p>
      <p>Te damos la bienvenida a nuestra comunidad de prevención para <code>{email}</code>. Nuestro objetivo es ayudarte a mantener tus pies sanos y evitar complicaciones.</p>
      
      <div class="tip">
        <strong>💡 Consejo clave de hoy:</strong>
        <p style="margin: 4px 0 0 0; font-size: 13px;">Revisá la planta de tus pies y entre los dedos todos los días con buena luz. Si te cuesta agacharte, podés usar un espejo de mano o pedirle ayuda a un familiar.</p>
      </div>

      <p>Recordá que si notás una ampolla, enrojecimiento o cambio de color, podés usar nuestro <strong>semáforo fotográfico gratuito</strong> en menos de 30 segundos:</p>

      <div style="text-align: center;">
        <a href="https://piediabetico.lat" class="btn">Probar el Triage Gratuito</a>
      </div>
    </div>
    <div class="footer">
      <p>© 2026 piediabetico.lat · Portal de Educación & Prevención</p>
      <p>Para cancelar tu suscripción gratis, hacé <a href="https://piediabetico.lat?unsubscribe={email}">clic aquí</a>.</p>
    </div>
  </div>
</body>
</html>"""


def get_template_confirmacion_contacto(ticket_id: str, nombre: str, motivo: str) -> str:
    return f"""<!DOCTYPE html>
<html lang="es">
<head>
  <meta charset="utf-8">
  <title>Ticket de Consulta #{ticket_id}</title>
  <style>
    body {{ font-family: -apple-system, BlinkMacSystemFont, 'Segoe UI', Roboto, sans-serif; background-color: #F8FAFC; margin: 0; padding: 0; color: #1E293B; }}
    .container {{ max-width: 550px; margin: 20px auto; background-color: #FFFFFF; border-radius: 16px; overflow: hidden; border: 1px solid #E2E8F0; }}
    .header {{ background: #1E3A8A; padding: 24px; text-align: center; color: #FFFFFF; }}
    .body {{ padding: 28px; font-size: 14px; line-height: 1.6; color: #334155; }}
    .ticket-badge {{ display: inline-block; background: #DBEAFE; color: #1E40AF; font-weight: 900; font-size: 16px; padding: 8px 16px; border-radius: 10px; margin: 12px 0; }}
    .footer {{ background: #F1F5F9; padding: 16px; text-align: center; font-size: 11px; color: #64748B; }}
  </style>
</head>
<body>
  <div class="container">
    <div class="header">
      <h2 style="margin:0;">piediabetico.lat</h2>
      <p style="margin:4px 0 0 0; font-size:12px; color:#93C5FD;">Mesa de Ayuda & Contacto Oficial</p>
    </div>
    <div class="body">
      <p>Hola <strong>{nombre}</strong>,</p>
      <p>Hemos recibido tu consulta sobre <strong>{motivo}</strong>.</p>
      
      <div style="text-align:center;">
        <span class="ticket-badge">Ticket: {ticket_id}</span>
      </div>

      <p>Nuestro equipo médico y de soporte responderá a este correo electrónico en un plazo máximo de <strong>24 a 48 horas hábiles</strong>.</p>
      <p>Gracias por contactarte con nosotros.</p>
    </div>
    <div class="footer">
      <p>© 2026 piediabetico.lat · Todos los derechos reservados.</p>
    </div>
  </div>
</body>
</html>"""


# ═══════════════════════════════════════════════════════════════════════
# MOTOR DE ENVÍO VIA RESEND REST API / SMTP
# ═══════════════════════════════════════════════════════════════════════

def enviar_email(to_email: str, subject: str, html_content: str) -> Dict[str, Any]:
    """
    Envía un correo electrónico utilizando la API de Resend (o simula con log si no hay clave configurada).
    """
    if not RESEND_API_KEY:
        logger.info(f"[SIMULACIÓN EMAIL RESEND] Para: {to_email} | Asunto: {subject} | Estado: ENVIADO_MOCK")
        return {"status": "success", "mode": "simulated", "message": f"Email simulado enviado a {to_email}"}

    url = "https://api.resend.com/emails"
    headers = {
        "Authorization": f"Bearer {RESEND_API_KEY}",
        "Content-Type": "application/json"
    }
    payload = {
        "from": FROM_EMAIL,
        "to": [to_email],
        "subject": subject,
        "html": html_content
    }

    try:
        req = urllib.request.Request(
            url,
            data=json.dumps(payload).encode("utf-8"),
            headers=headers,
            method="POST"
        )
        with urllib.request.urlopen(req, timeout=10) as response:
            res_data = json.loads(response.read().decode("utf-8"))
            logger.info(f"✓ Email enviado exitosamente a {to_email} vía Resend ID: {res_data.get('id')}")
            return {"status": "success", "id": res_data.get("id")}
    except Exception as e:
        logger.error(f"Error enviando email via Resend a {to_email}: {e}")
        return {"status": "error", "error": str(e)}


# ═══════════════════════════════════════════════════════════════════════
# PERSISTENCIA LOCAL DE SUSCRIPTORES Y CONSULTAS
# ═══════════════════════════════════════════════════════════════════════

def registrar_suscriptor(email: str, perfil: str = "profesional", pais: str = "LATAM") -> Dict[str, Any]:
    email_clean = email.strip().lower()
    suscriptores = []

    if os.path.exists(SUBSCRIPTORES_FILE):
        try:
            with open(SUBSCRIPTORES_FILE, "r", encoding="utf-8") as f:
                suscriptores = json.load(f)
        except Exception:
            suscriptores = []

    # Verificar si ya existe
    existe = any(s.get("email") == email_clean for s in suscriptores)
    if not existe:
        suscriptores.append({
            "email": email_clean,
            "perfil": perfil,
            "pais": pais,
            "fecha_alta": datetime.utcnow().isoformat() + "Z",
            "activo": True
        })
        with open(SUBSCRIPTORES_FILE, "w", encoding="utf-8") as f:
            json.dump(suscriptores, f, indent=2, ensure_ascii=False)

    # Disparar email de bienvenida según perfil
    if perfil == "paciente":
        subject = "🦶 Bienvenido al Boletín de Cuidado del Pie Diabético"
        html = get_template_bienvenida_paciente(email_clean)
    else:
        subject = "📚 Bienvenido a la Red Científica de piediabetico.lat"
        html = get_template_bienvenida_medico(email_clean)

    res_envio = enviar_email(email_clean, subject, html)
    return {
        "status": "success",
        "email": email_clean,
        "perfil": perfil,
        "email_enviado": res_envio.get("status") == "success"
    }


def registrar_consulta(nombre: str, email: str, tel: str, motivo: str, mensaje: str) -> Dict[str, Any]:
    import random
    ticket_id = f"CONS-{random.randint(1000, 9999)}"
    consultas = []

    if os.path.exists(CONSULTAS_FILE):
        try:
            with open(CONSULTAS_FILE, "r", encoding="utf-8") as f:
                consultas = json.load(f)
        except Exception:
            consultas = []

    consulta_obj = {
        "ticket_id": ticket_id,
        "nombre": nombre.strip(),
        "email": email.strip().lower(),
        "telefono": tel.strip(),
        "motivo": motivo,
        "mensaje": mensaje.strip(),
        "fecha": datetime.utcnow().isoformat() + "Z",
        "estado": "PENDIENTE_RESPUESTA"
    }
    consultas.append(consulta_obj)

    with open(CONSULTAS_FILE, "w", encoding="utf-8") as f:
        json.dump(consultas, f, indent=2, ensure_ascii=False)

    # Disparar email de confirmación
    subject = f"Confirmación de Consulta [{ticket_id}] · piediabetico.lat"
    html = get_template_confirmacion_contacto(ticket_id, nombre, motivo)
    enviar_email(email.strip().lower(), subject, html)

    return {"status": "success", "ticket_id": ticket_id}
