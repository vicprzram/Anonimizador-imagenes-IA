"""
Objetivo — motor de la aplicación web (Flask).

Sirve la interfaz y recibe la imagen que el usuario sube.
No hay análisis ni chat: solo el diseño y la subida.
"""

import os
import uuid
from flask import Flask, render_template, request, jsonify, send_from_directory

# ---------------------------------------------------------------------------
# Configuración
# ---------------------------------------------------------------------------
BASE_DIR = os.path.dirname(os.path.abspath(__file__))
UPLOAD_DIR = os.path.join(BASE_DIR, "uploads")
ALLOWED_EXTENSIONS = {"png", "jpg", "jpeg", "webp", "gif", "avif"}
MAX_CONTENT_LENGTH = 10 * 1024 * 1024  # 10 MB

os.makedirs(UPLOAD_DIR, exist_ok=True)

app = Flask(__name__, template_folder="static")
app.config["MAX_CONTENT_LENGTH"] = MAX_CONTENT_LENGTH


def extension_permitida(nombre: str) -> bool:
    return "." in nombre and nombre.rsplit(".", 1)[1].lower() in ALLOWED_EXTENSIONS


# ---------------------------------------------------------------------------
# Rutas
# ---------------------------------------------------------------------------
@app.route("/")
def inicio():
    return render_template("index.html")

@app.route("/images/<path:filename>")
def images(filename):
    return send_from_directory("images", filename)

@app.route("/upload", methods=["POST"])
def subir():
    if "imagen" not in request.files:
        return jsonify(ok=False, error="No se ha enviado ninguna imagen."), 400

    archivo = request.files["imagen"]

    if archivo.filename == "":
        return jsonify(ok=False, error="El archivo no tiene nombre."), 400

    if not extension_permitida(archivo.filename):
        return jsonify(ok=False, error="Formato no admitido. Usa PNG, JPG, WEBP o GIF."), 415

    # Guardamos con un nombre único para no pisar archivos anteriores.
    extension = archivo.filename.rsplit(".", 1)[1].lower()
    nombre_guardado = f"{uuid.uuid4().hex}.{extension}"
    archivo.save(os.path.join(UPLOAD_DIR, nombre_guardado))

    return jsonify(ok=True, archivo=nombre_guardado, original=archivo.filename)


@app.errorhandler(413)
def archivo_demasiado_grande(_):
    return jsonify(ok=False, error="La imagen supera el límite de 10 MB."), 413


if __name__ == "__main__":
    app.run(debug=True, port=5000)
