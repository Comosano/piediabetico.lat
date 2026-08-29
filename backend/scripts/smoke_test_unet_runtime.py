#!/usr/bin/env python3
"""
SMOKE TEST REAL DE RUNTIME PARA U-NET
Ejecuta la carga real con TensorFlow/Keras y una inferencia sintética (sin fotos clínicas).
"""
import os
import sys
import numpy as np

def run_smoke_test():
    print("================================================================")
    print("🔬 INICIANDO SMOKE TEST DE RUNTIME U-NET (KERAS / TENSORFLOW)")
    print("================================================================")

    # 1. Importar TensorFlow & Keras
    try:
        import tensorflow as tf
        from tensorflow.keras.models import load_model
        import tensorflow.keras.backend as K
        print(f"✓ TENSORFLOW IMPORT = PASS (v{tf.__version__})")
    except Exception as e:
        print(f"✕ TENSORFLOW IMPORT = FAIL ({e})")
        sys.exit(1)

    # 2. Definir custom metrics requeridas
    def dice_coef(y_true, y_pred):
        y_true_f = K.flatten(y_true)
        y_pred_f = K.flatten(y_pred)
        intersection = K.sum(y_true_f * y_pred_f)
        return (2. * intersection + K.epsilon()) / (K.sum(y_true_f) + K.sum(y_pred_f) + K.epsilon())

    def dice_loss(y_true, y_pred):
        return 1.0 - dice_coef(y_true, y_pred)

    # 3. Ubicación del modelo
    model_path = os.getenv(
        "UNET_MODELO_PATH",
        os.path.abspath(os.path.join(os.path.dirname(__file__), "..", "..", "modelos", "unet_wound_segmentation_model.keras"))
    )
    if not os.path.exists(model_path):
        # Probar path alternativo dentro de contenedor Docker
        if os.path.exists("/modelos/unet_wound_segmentation_model.keras"):
            model_path = "/modelos/unet_wound_segmentation_model.keras"
        elif os.path.exists("/app/modelos/unet_wound_segmentation_model.keras"):
            model_path = "/app/modelos/unet_wound_segmentation_model.keras"

    print(f"  Ruta física evaluada: {model_path}")
    print(f"  Existe en disco: {os.path.exists(model_path)} (Tamaño: {os.path.getsize(model_path)} bytes)")

    # 4. Cargar modelo real con load_model
    try:
        model = load_model(
            model_path,
            custom_objects={'dice_coef': dice_coef, 'dice_loss': dice_loss},
            compile=False
        )
        print("✓ KERAS LOAD_MODEL = PASS")
    except Exception as e:
        print(f"✕ KERAS LOAD_MODEL = FAIL ({e})")
        sys.exit(1)

    # 5. Dimensiones del modelo
    input_shape = model.input_shape
    output_shape = model.output_shape
    print(f"  MODEL INPUT SHAPE = {input_shape}")
    print(f"  MODEL OUTPUT SHAPE = {output_shape}")

    # 6. Crear imagen sintética no clínica de 256x256x3 (patrón geométrico sintético)
    synthetic_image = np.zeros((1, 256, 256, 3), dtype=np.float32)
    # Dibujar un cuadrado sintético centrado
    synthetic_image[0, 64:192, 64:192, :] = 0.8

    # 7. Inferencia real con model.predict()
    try:
        prediction = model.predict(synthetic_image, verbose=0)
        print("✓ REAL PREDICT = PASS")
    except Exception as e:
        print(f"✕ REAL PREDICT = FAIL ({e})")
        sys.exit(1)

    # 8. Post-procesamiento y generación de máscara binaria
    binary_mask = (prediction[0, :, :, 0] > 0.5).astype(np.uint8)
    pixel_area = int(np.sum(binary_mask > 0))
    total_pixels = 256 * 256
    rel_percent = round((pixel_area / total_pixels) * 100, 2)

    print(f"  MASK GENERATED = YES (Dimensiones: {binary_mask.shape})")
    print(f"  Área en píxeles detectada: {pixel_area} px")
    print(f"  Área relativa calculada: {rel_percent}%")
    print("================================================================")
    print("🏁 SMOKE TEST EXITOSO: U-NET REAL RUNTIME READY = YES")
    print("================================================================")

if __name__ == "__main__":
    run_smoke_test()
