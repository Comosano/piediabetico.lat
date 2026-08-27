"""
╔══════════════════════════════════════════════════════════════════════╗
║  CONVERSOR DE MODELO U-NET: KERAS (.keras) ➔ ONNX (.onnx)           ║
║  piediabetico.lat — Pipeline de Optimización                         ║
╚══════════════════════════════════════════════════════════════════════╝
Uso:
    python convertir_a_onnx.py
"""

import os
import sys

def convertir_unet_a_onnx():
    keras_path = os.path.join(os.path.dirname(__file__), "unet_wound_segmentation_model.keras")
    onnx_path = os.path.join(os.path.dirname(__file__), "dfu_segmentacion_unet.onnx")

    if not os.path.exists(keras_path):
        print(f"❌ Error: No se encontró el archivo {keras_path}")
        return False

    print(f"📦 Cargando modelo Keras desde: {keras_path}...")
    try:
        import tensorflow as tf
        import tf2onnx
        from tensorflow.keras.models import load_model
        import tensorflow.keras.backend as K

        def dice_coef(y_true, y_pred):
            y_true_f = K.flatten(y_true)
            y_pred_f = K.flatten(y_pred)
            intersection = K.sum(y_true_f * y_pred_f)
            return (2. * intersection + K.epsilon()) / (K.sum(y_true_f) + K.sum(y_pred_f) + K.epsilon())

        def dice_loss(y_true, y_pred):
            return 1.0 - dice_coef(y_true, y_pred)

        model = load_model(
            keras_path,
            custom_objects={'dice_coef': dice_coef, 'dice_loss': dice_loss},
            compile=False
        )
        print("✓ Modelo Keras cargado con éxito.")

        print(f"🔄 Convirtiendo a formato ONNX optimizado (opset 14)...")
        input_signature = [tf.TensorSpec([None, 256, 256, 3], tf.float32, name='image_input')]
        
        onnx_model, _ = tf2onnx.convert.from_keras(
            model,
            input_signature=input_signature,
            opset=14,
            output_path=onnx_path
        )

        print(f"🎉 ¡Conversión completada con éxito!")
        print(f"📁 Archivo ONNX generado en: {onnx_path}")
        return True

    except ImportError:
        print("⚠️ Nota: Para convertir a ONNX localmente se requiere tf2onnx y tensorflow.")
        print("   Comando: pip install tensorflow tf2onnx onnx")
        return False
    except Exception as e:
        print(f"❌ Error durante la conversión: {e}")
        return False

if __name__ == "__main__":
    convertir_unet_a_onnx()
