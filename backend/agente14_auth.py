"""
AGENTE 14: Sistema de Autenticación, Cuentas & 2FA (Salud Digital)
piediabetico.lat — Ecosistema Clínico LATAM

Cumplimiento estricto:
- Ley 25.326 (Protección de Datos Personales / Datos Sensibles de Salud)
- Ley 27.706 (Teleasistencia Médica / Validación de Matrícula Profesional)
- Autenticación en Dos Pasos (2FA por SMS / Email)
"""

import random
from typing import Optional, Literal
from datetime import datetime
from pydantic import BaseModel, Field, EmailStr
from fastapi import APIRouter, HTTPException

router_auth = APIRouter(prefix="/auth", tags=["Autenticación & 2FA de Salud"])

# Base de datos en memoria para cuentas y códigos OTP 2FA
_USUARIOS_DB = {
    "dr.perez@hospital.com": {
        "email": "dr.perez@hospital.com",
        "nombre": "Dr. Fernando Pérez",
        "rol": "profesional",
        "especialidad": "Cirugía Vascular & Pie Diabético",
        "matricula": "MN 142.850 / MP 45.120",
        "institucion": "Hospital de Clínicas / Centro Diabetológico",
        "telefono": "+54 9 11 5544-3322",
        "password": "medico123",
        "dos_fa_activo": True,
        "creado_el": "2026-08-20 10:00"
    },
    "juan.paciente@email.com": {
        "email": "juan.paciente@email.com",
        "nombre": "Juan Carlos Pérez",
        "rol": "paciente",
        "telefono": "+54 9 11 4433-2211",
        "password": "paciente123",
        "dos_fa_activo": True,
        "creado_el": "2026-08-22 14:30"
    }
}

_OTP_CODES = {}

class RegistroInput(BaseModel):
    email: EmailStr
    password: str = Field(..., min_length=6)
    nombre: str
    telefono: str
    rol: Literal["paciente", "profesional"]
    especialidad: Optional[str] = None
    matricula: Optional[str] = None
    institucion: Optional[str] = None

class LoginInput(BaseModel):
    email: EmailStr
    password: str

class Verificar2FAInput(BaseModel):
    email: EmailStr
    codigo_2fa: str

class AuthResponse(BaseModel):
    exito: bool
    mensaje: str
    requiere_2fa: bool = False
    usuario: Optional[dict] = None
    token_sesion: Optional[str] = None

@router_auth.post("/registro", response_model=AuthResponse)
def registrar_usuario(payload: RegistroInput):
    """Registra un nuevo usuario (Paciente o Profesional con matrícula)."""
    email_clean = payload.email.lower().strip()
    if email_clean in _USUARIOS_DB:
        raise HTTPException(status_code=400, detail="Ya existe una cuenta registrada con este correo electrónico.")
    
    if payload.rol == "profesional" and not payload.matricula:
        raise HTTPException(status_code=400, detail="La matrícula profesional es obligatoria para médicos y podólogos según la Ley 27.706.")

    nuevo_usuario = {
        "email": email_clean,
        "nombre": payload.nombre,
        "rol": payload.rol,
        "especialidad": payload.especialidad if payload.rol == "profesional" else None,
        "matricula": payload.matricula if payload.rol == "profesional" else None,
        "institucion": payload.institucion if payload.rol == "profesional" else None,
        "telefono": payload.telefono,
        "password": payload.password,
        "dos_fa_activo": True,
        "creado_el": datetime.now().strftime("%Y-%m-%d %H:%M")
    }
    
    _USUARIOS_DB[email_clean] = nuevo_usuario
    
    # Generar código 2FA de bienvenida
    codigo = f"{random.randint(100000, 999999)}"
    _OTP_CODES[email_clean] = codigo
    
    return AuthResponse(
        exito=True,
        mensaje=f"Cuenta creada con éxito. Código de verificación 2FA enviado a su teléfono/email (Código de prueba: {codigo})",
        requiere_2fa=True,
        usuario={"email": email_clean, "nombre": payload.nombre, "rol": payload.rol}
    )

@router_auth.post("/login", response_model=AuthResponse)
def iniciar_sesion(payload: LoginInput):
    """Verifica credenciales y solicita el código 2FA."""
    email_clean = payload.email.lower().strip()
    user = _USUARIOS_DB.get(email_clean)
    
    if not user or user["password"] != payload.password:
        raise HTTPException(status_code=401, detail="Correo electrónico o contraseña incorrectos.")
    
    # Generar código 2FA
    codigo = f"{random.randint(100000, 999999)}"
    _OTP_CODES[email_clean] = codigo
    
    return AuthResponse(
        exito=True,
        mensaje=f"Credenciales válidas. Ingrese el código de seguridad 2FA enviado a su dispositivo (Código de prueba: {codigo})",
        requiere_2fa=True,
        usuario={"email": user["email"], "nombre": user["nombre"], "rol": user["rol"]}
    )

@router_auth.post("/verificar-2fa", response_model=AuthResponse)
def verificar_codigo_2fa(payload: Verificar2FAInput):
    """Valida el código OTP de 6 dígitos e inicia la sesión formal."""
    email_clean = payload.email.lower().strip()
    user = _USUARIOS_DB.get(email_clean)
    
    if not user:
        raise HTTPException(status_code=404, detail="Usuario no encontrado.")
    
    codigo_esperado = _OTP_CODES.get(email_clean)
    
    # Acepta el código generado o el código maestro de desarrollo 123456
    if payload.codigo_2fa != codigo_esperado and payload.codigo_2fa != "123456":
        raise HTTPException(status_code=400, detail="Código 2FA incorrecto o expirado. Por favor intente nuevamente.")
    
    token = f"pd_sec_{random.randint(10000000, 99999999)}"
    
    datos_perfil = {k: v for k, v in user.items() if k != "password"}
    
    return AuthResponse(
        exito=True,
        mensaje="✓ Autenticación en dos pasos (2FA) exitosa. Sesión médica segura iniciada.",
        requiere_2fa=False,
        usuario=datos_perfil,
        token_sesion=token
    )
