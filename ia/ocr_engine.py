"""
Motor OCR — versión reutilizable para la app web.

A diferencia de `ocr.py` (script lineal de pruebas), aquí el modelo se carga
UNA sola vez al importar y se expone `procesar_imagen()`, que recibe una imagen
(ruta o array BGR) y devuelve:

    {
        "lecturas": [ {"texto", "score", "caja"} , ... ],   # texto reconocido fiable
        "imagen_anonimizada": np.ndarray (BGR),             # RX con el texto borrado
        "n_cajas": int,                                     # cajas detectadas por YOLO
    }

El borrado usa una máscara fina por trazos + inpaint, que reconstruye el fondo
local sin dejar parches de color plano (el problema del "manchurrón").
"""

from pathlib import Path
import cv2
import numpy as np

# ─────────────────────────── Configuración ───────────────────────────
ROOT = Path(__file__).resolve().parent          # .../ia
MODELO_PATH = ROOT.parent / "runs" / "detect" / "final-trained" / "weights" / "best.pt"
REC_MODEL_NAME = "PP-OCRv5_server_rec"

UMBRAL_SCORE = 0.5
YOLO_CONF = 0.25
YOLO_IMGSZ = 512

# ─────────────────── Carga perezosa de los modelos ───────────────────
# Se cargan la primera vez que se llama a procesar_imagen(), no al importar,
# para que la app web arranque rápido y no falle en import si faltan pesos.
_model = None
_rec = None
_carga_error = None


def _cargar_modelos():
    global _model, _rec, _carga_error
    if _model is not None and _rec is not None:
        return True
    if _carga_error is not None:
        return False
    try:
        from ultralytics import YOLO
        from paddleocr import TextRecognition

        if not MODELO_PATH.exists():
            raise FileNotFoundError(
                f"No se encontró el modelo YOLO en: {MODELO_PATH}"
            )
        _model = YOLO(str(MODELO_PATH))
        _rec = TextRecognition(model_name=REC_MODEL_NAME)
        return True
    except Exception as e:  # noqa: BLE001
        _carga_error = e
        return False


# ─────────────────────────── Preprocesado ────────────────────────────
def _base(recorte, escala=6, pad=15):
    h, w = recorte.shape[:2]
    r = cv2.resize(recorte, (w * escala, h * escala), interpolation=cv2.INTER_LANCZOS4)
    return cv2.copyMakeBorder(r, pad, pad, pad, pad, cv2.BORDER_CONSTANT, value=(0, 0, 0))


def _unsharp(gris, sigma=1.0, amount=1.5):
    blur = cv2.GaussianBlur(gris, (0, 0), sigma)
    return cv2.addWeighted(gris, 1 + amount, blur, -amount, 0)


def variantes_normales(recorte):
    base = _base(recorte)
    gris = cv2.cvtColor(base, cv2.COLOR_BGR2GRAY)
    v1 = base
    g = cv2.normalize(gris, None, 0, 255, cv2.NORM_MINMAX)
    g = cv2.createCLAHE(clipLimit=4.0, tileGridSize=(8, 8)).apply(g)
    g = _unsharp(g)
    v2 = cv2.cvtColor(g, cv2.COLOR_GRAY2BGR)
    v3 = cv2.cvtColor(cv2.bitwise_not(g), cv2.COLOR_GRAY2BGR)
    return [v1, v2, v3]


def variantes_extremas(recorte, escala=8, pad=20):
    """V4-V5: para texto casi invisible (blanco sobre blanco)."""
    gris = cv2.cvtColor(recorte, cv2.COLOR_BGR2GRAY).astype(np.float32)

    lo, hi = np.percentile(gris, 1), np.percentile(gris, 99)
    if hi - lo < 1:
        lo, hi = gris.min(), gris.max()
    g = np.clip((gris - lo) / max(hi - lo, 1e-6) * 255, 0, 255).astype(np.uint8)

    h, w = g.shape
    g = cv2.resize(g, (w * escala, h * escala), interpolation=cv2.INTER_LANCZOS4)
    g = cv2.createCLAHE(clipLimit=8.0, tileGridSize=(4, 4)).apply(g)
    _, g = cv2.threshold(g, 0, 255, cv2.THRESH_BINARY + cv2.THRESH_OTSU)
    g = cv2.morphologyEx(g, cv2.MORPH_CLOSE, np.ones((2, 2), np.uint8))
    g = cv2.copyMakeBorder(g, pad, pad, pad, pad, cv2.BORDER_CONSTANT, value=0)

    return [cv2.cvtColor(g, cv2.COLOR_GRAY2BGR),
            cv2.cvtColor(cv2.bitwise_not(g), cv2.COLOR_GRAY2BGR)]


def correccion_iluminacion(recorte, escala=8, pad=20):
    """Texto sobre fondo de brillo MUY irregular (zona quemada de la RX)."""
    gris = cv2.cvtColor(recorte, cv2.COLOR_BGR2GRAY)
    h, w = gris.shape
    gris = cv2.resize(gris, (w * escala, h * escala), interpolation=cv2.INTER_LANCZOS4)

    k = max(gris.shape) // 8 | 1
    fondo = cv2.GaussianBlur(gris, (0, 0), sigmaX=k)
    norm = cv2.divide(gris, fondo, scale=255)

    norm = cv2.createCLAHE(clipLimit=4.0, tileGridSize=(8, 8)).apply(norm)
    _, b = cv2.threshold(norm, 0, 255, cv2.THRESH_BINARY + cv2.THRESH_OTSU)
    b = cv2.morphologyEx(b, cv2.MORPH_CLOSE, np.ones((2, 2), np.uint8))
    b = cv2.copyMakeBorder(b, pad, pad, pad, pad, cv2.BORDER_CONSTANT, value=0)

    return [cv2.cvtColor(b, cv2.COLOR_GRAY2BGR),
            cv2.cvtColor(cv2.bitwise_not(b), cv2.COLOR_GRAY2BGR)]


def expandir(x1, y1, x2, y2, m, shape):
    H, W = shape[:2]
    return max(0, x1 - m), max(0, y1 - m), min(W, x2 + m), min(H, y2 + m)


# ─────────────────────────── Borrado ─────────────────────────────────
def borrar_texto(img, cajas_xyxy, margen=3, k=22, dilatar=2, inpaint_radius=3):
    """
    Borra las regiones de texto reconstruyendo el fondo local con inpaint.

    Construye una máscara FINA (solo los píxeles de los trazos, no el rectángulo
    entero) y aplica cv2.inpaint, que propaga el fondo de alrededor. Así no quedan
    parches de color plano ni bloques de tono distinto.

    margen         -> píxeles extra alrededor de cada caja (antialiasing del borde).
    k              -> umbral: cuánto se separa un píxel del fondo para ser "texto".
    dilatar        -> engorda la máscara para coger el halo del trazo.
    inpaint_radius -> radio de reconstrucción de cv2.inpaint.
    """
    H, W = img.shape[:2]
    gris = cv2.cvtColor(img, cv2.COLOR_BGR2GRAY)
    mask = np.zeros((H, W), np.uint8)

    for (x1, y1, x2, y2) in cajas_xyxy:
        x1m, y1m = max(0, int(x1) - margen), max(0, int(y1) - margen)
        x2m, y2m = min(W, int(x2) + margen), min(H, int(y2) + margen)

        box_gray = gris[y1m:y2m, x1m:x2m]
        if box_gray.size == 0:
            continue

        # fondo de referencia = mediana del anillo de borde de la caja
        ring = np.concatenate([box_gray[0, :], box_gray[-1, :],
                               box_gray[:, 0], box_gray[:, -1]])
        bg = np.median(ring)

        # máscara fina: píxeles que se desvían del fondo en cualquier dirección
        m = (np.abs(box_gray.astype(np.int16) - bg) > k).astype(np.uint8) * 255
        if dilatar:
            m = cv2.dilate(m, np.ones((dilatar, dilatar), np.uint8))

        mask[y1m:y2m, x1m:x2m] = np.maximum(mask[y1m:y2m, x1m:x2m], m)

    if not mask.any():
        return img.copy()

    return cv2.inpaint(img, mask, inpaint_radius, cv2.INPAINT_TELEA)


# ─────────────────────────── API pública ─────────────────────────────
def procesar_imagen(imagen, borrar_todas=True):
    """
    Procesa una imagen y devuelve el texto reconocido + la imagen anonimizada.

    imagen        -> ruta (str/Path) o np.ndarray BGR.
    borrar_todas  -> True: borra TODAS las cajas que YOLO marcó como texto
                     (recomendado para anonimizar, aunque el OCR no las lea bien).
                     False: borra solo las lecturas con score >= UMBRAL_SCORE.

    Devuelve un dict (ver cabecera del módulo).
    Lanza RuntimeError si los modelos no se pudieron cargar.
    """
    if not _cargar_modelos():
        raise RuntimeError(f"No se pudieron cargar los modelos OCR: {_carga_error}")

    # --- cargar imagen ---
    if isinstance(imagen, (str, Path)):
        img = cv2.imread(str(imagen))
        if img is None:
            raise FileNotFoundError(f"No se pudo leer la imagen: {imagen}")
    else:
        img = imagen
        if img is None or not hasattr(img, "shape"):
            raise ValueError("La imagen recibida no es válida.")

    # --- detección de cajas con YOLO ---
    resultados = _model(img, conf=YOLO_CONF, imgsz=YOLO_IMGSZ, verbose=False)
    cajas = resultados[0].boxes.xyxy.cpu().numpy().astype(int)

    lecturas = []
    cajas_para_borrar = []

    for (x1, y1, x2, y2) in cajas:
        ex1, ey1, ex2, ey2 = expandir(x1, y1, x2, y2, 3, img.shape)
        recorte = img[ey1:ey2, ex1:ex2]
        if recorte.size == 0:
            continue

        vs = (variantes_normales(recorte)
              + variantes_extremas(recorte)
              + correccion_iluminacion(recorte))

        out = _rec.predict(vs, batch_size=len(vs))
        scores = [r.get("rec_score", 0.0) for r in out]
        best = int(np.argmax(scores))
        texto, score = out[best].get("rec_text", ""), float(scores[best])

        if score >= UMBRAL_SCORE:
            lecturas.append({
                "texto": texto,
                "score": round(score, 3),
                "caja": [int(x1), int(y1), int(x2), int(y2)],
            })

    # --- decidir qué cajas borrar ---
    if borrar_todas:
        cajas_para_borrar = cajas
    else:
        cajas_para_borrar = [l["caja"] for l in lecturas]

    imagen_anonimizada = borrar_texto(img, cajas_para_borrar)

    # cajas normalizadas (0..1) para dibujarlas sobre la imagen en el frontend,
    # sea cual sea el tamaño con el que se muestre
    H, W = img.shape[:2]
    cajas_norm = [
        {
            "x": round(float(x1) / W, 5),
            "y": round(float(y1) / H, 5),
            "w": round(float(x2 - x1) / W, 5),
            "h": round(float(y2 - y1) / H, 5),
        }
        for (x1, y1, x2, y2) in cajas_para_borrar
    ]

    return {
        "lecturas": lecturas,
        "imagen_anonimizada": imagen_anonimizada,
        "n_cajas": int(len(cajas)),
        "cajas_norm": cajas_norm,
    }


def modelos_disponibles():
    """Comprueba si los modelos se pueden cargar (para un health-check)."""
    return _cargar_modelos()
