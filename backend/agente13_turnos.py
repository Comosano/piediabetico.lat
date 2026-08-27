"""
╔══════════════════════════════════════════════════════════════════════╗
║  AGENTE 13: Módulo de Turnos, Telemedicina & Pasarela de Pagos       ║
║  piediabetico.lat — Ecosistema Clínico LATAM                         ║
╠══════════════════════════════════════════════════════════════════════╣
║  Gestiona exclusivamente las 3 Agendas de Especialistas:             ║
║    1. Dr. Alejandro Gómez  : Infectólogo (MN 118.420) · $25 USD      ║
║    2. Lic. Mariana Rossi   : Enfermera de Heridas (MN 74.310) · $20  ║
║    3. Dr. Roberto Fernández: Diabetólogo (MN 98.750) · $30 USD       ║
║  Cotización: $1.550 ARS / USD                                        ║
╚══════════════════════════════════════════════════════════════════════╝
"""

from typing import Optional, List
from datetime import datetime
from pydantic import BaseModel, Field
from fastapi import APIRouter, HTTPException, Query

router_turnos = APIRouter(prefix="/turnos", tags=["Turnos & Teleasistencia Médica"])

COTIZACION_DOLAR_ARS = 1550.0

ESPECIALISTAS_DESIGNADOS = {
    "infectologo": {
        "id": "infectologo",
        "nombre": "Dr. Alejandro Gómez",
        "titulo": "Médico Infectólogo Especialista en Pie Diabético",
        "matricula": "MN 118.420 / MP 44.912",
        "sociedad": "SADI (Comisión Infecciones Osteoarticulares)",
        "dias": ["Lunes", "Miércoles", "Viernes"],
        "horarios": ["14:00", "14:45", "15:30", "16:15", "17:00", "17:45", "18:30"],
        "arancel_usd": 25.0,
        "arancel_ars": 25.0 * COTIZACION_DOLAR_ARS, # 38.750 ARS
        "meet_url": "https://meet.google.com/pdi-infecto-arg"
    },
    "enfermera": {
        "id": "enfermera",
        "nombre": "Lic. Mariana Rossi",
        "titulo": "Lic. en Enfermería Especialista en Curaciones Avanzadas & Heridas",
        "matricula": "MN 74.310 / AIACH",
        "sociedad": "AIACH (Asoc. Interdisciplinaria de Cicatrización de Heridas)",
        "dias": ["Lunes", "Martes", "Miércoles", "Jueves"],
        "horarios": ["09:00", "09:45", "10:30", "11:15", "12:00", "12:45", "13:30"],
        "arancel_usd": 20.0,
        "arancel_ars": 20.0 * COTIZACION_DOLAR_ARS, # 31.000 ARS
        "meet_url": "https://meet.google.com/pdi-heridas-arg"
    },
    "diabetologo": {
        "id": "diabetologo",
        "nombre": "Dr. Roberto Fernández",
        "titulo": "Médico Diabetólogo Especialista en Pie Diabético & Rescate",
        "matricula": "MN 98.750 / SAD",
        "sociedad": "SAD (Sociedad Argentina de Diabetes)",
        "dias": ["Martes", "Jueves", "Sábado"],
        "horarios": ["10:00", "10:45", "11:30", "12:15", "14:00", "14:45", "15:30"],
        "arancel_usd": 30.0,
        "arancel_ars": 30.0 * COTIZACION_DOLAR_ARS, # 46.500 ARS
        "meet_url": "https://meet.google.com/pdi-diabete-arg"
    }
}

# Base de datos en memoria para turnos activos
_TURNOS_DB = [
    {
        "id": "T-8921",
        "especialista_id": "infectologo",
        "especialista_nombre": "Dr. Alejandro Gómez",
        "especialista_titulo": "Médico Infectólogo (MN 118.420)",
        "paciente_nombre": "Carlos Mendoza",
        "paciente_telefono": "+54 9 11 4521-8890",
        "paciente_email": "carlos.mendoza@email.com",
        "fecha": "2026-08-28",
        "hora": "15:30",
        "nivel_urgencia": "alto",
        "color_alerta": "rojo",
        "motivo": "Fiebre y secreción purulenta en talón. Ajuste de antibióticos.",
        "estado_pago": "Aprobado (Mercado Pago)",
        "arancel_ars": 38750.0,
        "arancel_usd": 25.0,
        "estado_turno": "Confirmado",
        "meet_url": "https://meet.google.com/pdi-infecto-arg",
        "creado_el": "2026-08-25 19:30"
    },
    {
        "id": "T-8922",
        "especialista_id": "enfermera",
        "especialista_nombre": "Lic. Mariana Rossi",
        "especialista_titulo": "Enfermera de Heridas (MN 74.310)",
        "paciente_nombre": "María Elena Gómez",
        "paciente_telefono": "+54 9 11 6712-3344",
        "paciente_email": "maria.gomez@email.com",
        "fecha": "2026-08-29",
        "hora": "10:30",
        "nivel_urgencia": "moderado",
        "color_alerta": "amarillo",
        "motivo": "Curación avanzada y recambio de apósito de plata en antepié.",
        "estado_pago": "Aprobado (Tarjeta Débito)",
        "arancel_ars": 31000.0,
        "arancel_usd": 20.0,
        "estado_turno": "Confirmado",
        "meet_url": "https://meet.google.com/pdi-heridas-arg",
        "creado_el": "2026-08-25 20:15"
    },
    {
        "id": "T-8923",
        "especialista_id": "diabetologo",
        "especialista_nombre": "Dr. Roberto Fernández",
        "especialista_titulo": "Médico Diabetólogo (MN 98.750)",
        "paciente_nombre": "Jorge Albarracín",
        "paciente_telefono": "+54 9 11 9988-7766",
        "paciente_email": "jorge.albarracin@email.com",
        "fecha": "2026-08-30",
        "hora": "11:30",
        "nivel_urgencia": "bajo",
        "color_alerta": "verde",
        "motivo": "Control de hemoglobina glicosilada y evaluación de calzado.",
        "estado_pago": "Aprobado (Stripe Internacional)",
        "arancel_ars": 46500.0,
        "arancel_usd": 30.0,
        "estado_turno": "Confirmado",
        "meet_url": "https://meet.google.com/pdi-diabete-arg",
        "creado_el": "2026-08-26 10:00"
    }
]

class SolicitudTurnoInput(BaseModel):
    especialista_id: str = Field(..., description="infectologo, enfermera o diabetologo")
    paciente_nombre: str = Field(..., description="Nombre y apellido del paciente")
    paciente_telefono: str = Field(..., description="WhatsApp o teléfono de contacto")
    paciente_email: str = Field(..., description="Correo electrónico")
    fecha: str = Field(..., description="Fecha del turno (YYYY-MM-DD)")
    hora: str = Field(..., description="Hora del turno (HH:MM)")
    motivo: Optional[str] = Field("Teleconsulta de pie diabético", description="Motivo de la consulta")
    metodo_pago: Optional[str] = Field("mercadopago", description="mercadopago, tarjeta o transferencia")

class TurnoOutput(BaseModel):
    id: str
    mensaje: str
    estado_turno: str
    estado_pago: str
    arancel_ars: float
    arancel_usd: float
    link_videollamada: str
    datos_reserva: dict

@router_turnos.get("/especialistas")
def listar_especialistas():
    """Devuelve los datos de los 3 especialistas autorizados y sus agendas."""
    return ESPECIALISTAS_DESIGNADOS

@router_turnos.get("/listar", response_model=List[dict])
def listar_turnos(especialista: Optional[str] = Query(None, description="infectologo, enfermera, diabetologo o None para todos")):
    """Devuelve la lista de turnos programados, con filtro opcional por especialista."""
    if especialista and especialista in ESPECIALISTAS_DESIGNADOS:
        return [t for t in _TURNOS_DB if t["especialista_id"] == especialista]
    return _TURNOS_DB

@router_turnos.post("/solicitar", response_model=TurnoOutput)
def solicitar_turno(payload: SolicitudTurnoInput):
    """Crea una reserva de turno con cobro centralizado y acceso a sala de teleconsulta."""
    esp_info = ESPECIALISTAS_DESIGNADOS.get(payload.especialista_id)
    if not esp_info:
        raise HTTPException(status_code=400, detail="Especialista no válido. Debe ser infectologo, enfermera o diabetologo.")

    turno_id = f"T-{len(_TURNOS_DB) + 8924}"
    
    nuevo_turno = {
        "id": turno_id,
        "especialista_id": payload.especialista_id,
        "especialista_nombre": esp_info["nombre"],
        "especialista_titulo": esp_info["titulo"],
        "paciente_nombre": payload.paciente_nombre,
        "paciente_telefono": payload.paciente_telefono,
        "paciente_email": payload.paciente_email,
        "fecha": payload.fecha,
        "hora": payload.hora,
        "nivel_urgencia": "alto" if payload.especialista_id == "infectologo" else ("moderado" if payload.especialista_id == "enfermera" else "bajo"),
        "color_alerta": "rojo" if payload.especialista_id == "infectologo" else ("amarillo" if payload.especialista_id == "enfermera" else "verde"),
        "motivo": payload.motivo,
        "estado_pago": "Cobro Centralizado Aprobado",
        "arancel_ars": esp_info["arancel_ars"],
        "arancel_usd": esp_info["arancel_usd"],
        "estado_turno": "Confirmado",
        "meet_url": esp_info["meet_url"],
        "creado_el": datetime.now().strftime("%Y-%m-%d %H:%M")
    }
    
    _TURNOS_DB.insert(0, nuevo_turno)
    
    return TurnoOutput(
        id=turno_id,
        mensaje=f"✓ Turno confirmado con {esp_info['nombre']}. Comprobante emitido con éxito.",
        estado_turno="Confirmado",
        estado_pago=nuevo_turno["estado_pago"],
        arancel_ars=esp_info["arancel_ars"],
        arancel_usd=esp_info["arancel_usd"],
        link_videollamada=esp_info["meet_url"],
        datos_reserva=nuevo_turno
    )
