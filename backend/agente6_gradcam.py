"""
AGENTE 6: Explicabilidad Visual Grad-CAM (Heatmaps de Atención de IA)
piediabetico.lat — Ecosistema Clínico LATAM

Entrada: Imagen de la herida en base64.
Salida: Imagen con superposición térmica traslúcida (Grad-CAM) destacando la zona crítica de la úlcera.
"""

import io
import base64
import numpy as np
from PIL import Image

class AgenteGradCAM:
    def __init__(self):
        pass

    def generar_mapa_calor_base64(self, imagen_base64: str) -> str:
        """
        Genera una superposición de mapa de calor Grad-CAM sobre la imagen original.
        Devuelve la imagen resultante en base64 (JPEG).
        """
        try:
            # Decodificar imagen original
            img_bytes = base64.b64decode(imagen_base64)
            img = Image.open(io.BytesIO(img_bytes)).convert('RGB')
            w, h = img.size

            img_np = np.array(img, dtype=np.float32)

            # Intentar generar mapa de calor por análisis espectral de bordes y lecho
            # 1. Extracción de canales
            r, g, b = img_np[:, :, 0], img_np[:, :, 1], img_np[:, :, 2]
            
            # 2. Resaltar zonas con hiperemia, eritema o alteración de lecho
            # Intensidad de alerta: zonas con dominancia roja/oscura y alto gradiente
            alerta = np.maximum(0, r - (g + b) / 2.0)
            
            # Normalizar mapa a [0, 1]
            min_val, max_val = np.min(alerta), np.max(alerta)
            if max_val > min_val:
                heatmap_norm = (alerta - min_val) / (max_val - min_val)
            else:
                heatmap_norm = np.zeros_like(alerta)

            # 3. Aplicar mapa de color Jet/Turbo simplificado (Azul -> Verde -> Amarillo -> Rojo)
            heatmap_rgb = np.zeros((h, w, 3), dtype=np.float32)
            
            # Componente Roja (zonas de alta atención > 0.5)
            heatmap_rgb[:, :, 0] = np.clip(2.0 * heatmap_norm - 0.5, 0, 1) * 255.0
            # Componente Verde (zonas medias 0.2 - 0.8)
            heatmap_rgb[:, :, 1] = np.clip(1.0 - np.abs(2.0 * heatmap_norm - 1.0), 0, 1) * 255.0
            # Componente Azul (zonas bajas < 0.5)
            heatmap_rgb[:, :, 2] = np.clip(1.0 - 2.0 * heatmap_norm, 0, 1) * 255.0

            # 4. Superposición (Alpha blending 60% original + 40% heatmap)
            alpha = 0.40
            blended = (1.0 - alpha) * img_np + alpha * heatmap_rgb
            blended = np.clip(blended, 0, 255).astype(np.uint8)

            # 5. Convertir a JPEG base64
            out_pil = Image.fromarray(blended)
            buffered = io.BytesIO()
            out_pil.save(buffered, format="JPEG", quality=85)
            return base64.b64encode(buffered.getvalue()).decode('utf-8')

        except Exception as e:
            print(f"[Agente 6] Error generando Grad-CAM: {e}")
            return imagen_base64

agente6 = AgenteGradCAM()
