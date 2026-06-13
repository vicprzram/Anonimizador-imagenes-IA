from ultralytics import YOLO
from paddleocr import TextRecognition
from pathlib import Path
import cv2
import numpy as np

# ─────────────────────────── Configuración ───────────────────────────
root = Path("data") / "hackathon_TREE_AIBiomed"
model = YOLO("runs/detect/runs/train/yolov12_texto-5/weights/best.pt")
rec = TextRecognition(model_name="PP-OCRv5_server_rec")

UMBRAL_SCORE = 0.5
GUARDAR_DEBUG = True

# ⬇️⬇️ CAMBIA ESTO por el nombre de tu imagen ilegible ⬇️⬇️
img_path = root / "images" / "test" / "8df1bc0a-1f93728a-1f356bcc-5bfe1147-ab211251_annotated.png"


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

    # 1. Estira SOLO la franja donde vive el texto
    lo, hi = np.percentile(gris, 1), np.percentile(gris, 99)
    if hi - lo < 1:
        lo, hi = gris.min(), gris.max()
    g = np.clip((gris - lo) / max(hi - lo, 1e-6) * 255, 0, 255).astype(np.uint8)

    # 2. Escalado grande
    h, w = g.shape
    g = cv2.resize(g, (w * escala, h * escala), interpolation=cv2.INTER_LANCZOS4)

    # 3. CLAHE muy agresivo
    g = cv2.createCLAHE(clipLimit=8.0, tileGridSize=(4, 4)).apply(g)

    # 4. Binarización Otsu
    _, g = cv2.threshold(g, 0, 255, cv2.THRESH_BINARY + cv2.THRESH_OTSU)

    # 5. Une trazos rotos y limpia motas
    g = cv2.morphologyEx(g, cv2.MORPH_CLOSE, np.ones((2, 2), np.uint8))
    g = cv2.copyMakeBorder(g, pad, pad, pad, pad, cv2.BORDER_CONSTANT, value=0)

    return [cv2.cvtColor(g, cv2.COLOR_GRAY2BGR),
            cv2.cvtColor(cv2.bitwise_not(g), cv2.COLOR_GRAY2BGR)]


def expandir(x1, y1, x2, y2, m, shape):
    H, W = shape[:2]
    return max(0, x1 - m), max(0, y1 - m), min(W, x2 + m), min(H, y2 + m)


def diagnostico(recorte):
    """¿Hay señal recuperable? (min, max, n_valores_únicos)."""
    g = cv2.cvtColor(recorte, cv2.COLOR_BGR2GRAY)
    return int(g.min()), int(g.max()), len(np.unique(g))

def correccion_iluminacion(recorte, escala=8, pad=20):
    """Texto sobre fondo de brillo MUY irregular (zona quemada de la RX)."""
    gris = cv2.cvtColor(recorte, cv2.COLOR_BGR2GRAY)
    h, w = gris.shape
    gris = cv2.resize(gris, (w * escala, h * escala), interpolation=cv2.INTER_LANCZOS4)

    # 1. Estima el fondo con un desenfoque grande y DIVIDE -> aplana el gradiente
    k = max(gris.shape) // 8 | 1          # sigma grande, relativo al tamaño
    fondo = cv2.GaussianBlur(gris, (0, 0), sigmaX=k)
    norm = cv2.divide(gris, fondo, scale=255)

    # 2. Con el fondo ya uniforme, realza y binariza
    norm = cv2.createCLAHE(clipLimit=4.0, tileGridSize=(8, 8)).apply(norm)
    _, b = cv2.threshold(norm, 0, 255, cv2.THRESH_BINARY + cv2.THRESH_OTSU)
    b = cv2.morphologyEx(b, cv2.MORPH_CLOSE, np.ones((2, 2), np.uint8))
    b = cv2.copyMakeBorder(b, pad, pad, pad, pad, cv2.BORDER_CONSTANT, value=0)

    return [cv2.cvtColor(b, cv2.COLOR_GRAY2BGR),
            cv2.cvtColor(cv2.bitwise_not(b), cv2.COLOR_GRAY2BGR)]
    
# ─────────────────────────── Procesado ───────────────────────────────
resultados = model(str(img_path), conf=0.25, imgsz=512)
img = cv2.imread(str(img_path))

if img is None:
    raise FileNotFoundError(f"No se pudo leer la imagen: {img_path}")

cajas = resultados[0].boxes.xyxy.cpu().numpy().astype(int)
print(f"YOLO detectó {len(cajas)} cajas en {img_path.name}\n")

lecturas = []

for i, (x1, y1, x2, y2) in enumerate(cajas):
    ex1, ey1, ex2, ey2 = expandir(x1, y1, x2, y2, 3, img.shape)
    recorte = img[ey1:ey2, ex1:ex2]

    mn, mx, n = diagnostico(recorte)
    vs = variantes_normales(recorte) + variantes_extremas(recorte) + correccion_iluminacion(recorte)

    out = rec.predict(vs, batch_size=len(vs))
    scores = [r.get('rec_score', 0.0) for r in out]
    best = int(np.argmax(scores))
    texto, score = out[best].get('rec_text', ''), scores[best]

    if GUARDAR_DEBUG:
        for k, v in enumerate(vs):
            cv2.imwrite(f"debug_caja_{i}_v{k}.png", v)

    marca = "OK" if score >= UMBRAL_SCORE else "DESCARTADO"
    print(f"Caja {i} ({x1},{y1},{x2},{y2}) [min={mn} max={mx} únicos={n}] "
          f"→ '{texto}'  score={score:.2f}  var=V{best+1}  [{marca}]")

    if score >= UMBRAL_SCORE:
        lecturas.append(((x1, y1, x2, y2), texto, score))

print(f"\n{len(lecturas)} lecturas fiables de {len(cajas)} cajas.")