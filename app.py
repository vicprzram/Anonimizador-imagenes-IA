"""
Objetivo — motor de la aplicación web (Flask).

Sirve la interfaz, recibe la imagen que el usuario sube, la pasa por el OCR
(detección YOLO + reconocimiento PaddleOCR) y devuelve:
  - el texto reconocido en la imagen
  - la imagen anonimizada (con los datos del paciente borrados)
"""

from os import path, makedirs
from base64 import b64encode

import cv2
import numpy as np
from flask import Flask, render_template, request, jsonify, send_from_directory

# ---------------------------------------------------------------------------
# Configuración
# ---------------------------------------------------------------------------
BASE_DIR = path.dirname(path.abspath(__file__))
UPLOAD_DIR = path.join(BASE_DIR, "uploads")
ALLOWED_EXTENSIONS = {"png", "jpg", "jpeg", "webp"}
MAX_CONTENT_LENGTH = 10 * 1024 * 1024  # 10 MB

makedirs(UPLOAD_DIR, exist_ok=True)

app = Flask(__name__, template_folder="static")
app.config["MAX_CONTENT_LENGTH"] = MAX_CONTENT_LENGTH


def extension_permitida(nombre: str) -> bool:
    return "." in nombre and nombre.rsplit(".", 1)[1].lower() in ALLOWED_EXTENSIONS


def leer_imagen(archivo):
    """Lee un FileStorage de Flask a un array BGR de OpenCV (sin tocar disco)."""
    datos = np.frombuffer(archivo.read(), np.uint8)
    archivo.seek(0)
    return cv2.imdecode(datos, cv2.IMREAD_COLOR)


def png_a_base64(img) -> str:
    """Codifica una imagen BGR como data-URL PNG lista para <img src>."""
    ok, buf = cv2.imencode(".png", img)
    if not ok:
        raise RuntimeError("No se pudo codificar la imagen de salida.")
    b64 = b64encode(buf.tobytes()).decode("ascii")
    return f"data:image/png;base64,{b64}"


# ---------------------------------------------------------------------------
# Rutas
# ---------------------------------------------------------------------------
@app.route("/")
def inicio():
    return render_template("index.html")


@app.route("/images/<path:filename>")
def images(filename):
    return send_from_directory("images", filename)


@app.route("/anonimizar", methods=["POST"])
def anonimizar():
    """Recibe la imagen, la pasa por el OCR y devuelve texto + imagen limpia."""
    if "imagen" not in request.files:
        return jsonify(ok=False, error="No se ha enviado ninguna imagen."), 400

    archivo = request.files["imagen"]

    if archivo.filename == "":
        return jsonify(ok=False, error="El archivo no tiene nombre."), 400

    if not extension_permitida(archivo.filename):
        return jsonify(ok=False, error="Formato no admitido. Usa PNG, JPG, WEBP o GIF."), 415

    img = leer_imagen(archivo)
    if img is None:
        return jsonify(ok=False, error="No se pudo decodificar la imagen."), 400

    # Importación diferida: los modelos solo se cargan al primer uso real.
    try:
        from ia.ocr_engine import procesar_imagen
        resultado = procesar_imagen(img, borrar_todas=True)
    except Exception as e:  # noqa: BLE001
        app.logger.exception("Fallo en el OCR")
        return jsonify(ok=False, error=f"Error procesando la imagen: {e}"), 500

    lecturas = resultado["lecturas"]
    textos = [l["texto"] for l in lecturas if l["texto"].strip()]

    return jsonify(
        ok=True,
        original=archivo.filename,
        n_cajas=resultado["n_cajas"],
        n_lecturas=len(lecturas),
        textos=textos,                       # lista de cadenas reconocidas
        lecturas=lecturas,                   # detalle (texto, score, caja)
        cajas=resultado["cajas_norm"],       # cajas normalizadas (0..1) para dibujar
        imagen=png_a_base64(resultado["imagen_anonimizada"]),  # data-URL PNG
    )


@app.errorhandler(413)
def archivo_demasiado_grande(_):
    return jsonify(ok=False, error="La imagen supera el límite de 10 MB."), 413


if __name__ == "__main__":
    app.run(debug=True, port=5000)
