from ultralytics import YOLO
from pathlib import Path

# ============================================================
# 1. CONFIGURACION
# ============================================================
YAML_PATH = Path("./ia/conf/data.yaml")

# ============================================================
# 2. CARGAR MODELO
# ============================================================
MODEL = YOLO("./ia/conf/yolo12s.pt")   

# ============================================================
# 3. ENTRENAR
# ============================================================
if __name__ == "__main__":    
    MODEL.train(
        # --- Datos ---
        data=str(YAML_PATH),         # el data.yaml de la carpeta espejo

        # --- Duración ---
        epochs=100,                  # 150–300 suele ser razonable; ajusta según convergencia
        patience=15,                 # early stopping si no mejora en 30 epochs

        # --- Imagen y batch ---
        imgsz=512,                   # tamaño de entrada (640 estándar, 1280 para texto pequeño)
        batch=32,                    # ajusta según tu VRAM (ver tabla abajo)

        # --- Hardware ---
        device=0,                    # 0 = primera GPU; [0,1] para multi-GPU; "cpu" sin GPU
        workers=8,                   # hilos de carga de datos (8 está bien para la mayoría)
        amp=True,                    # mixed precision: más rápido y menos VRAM

        # --- Optimizador ---
        optimizer="AdamW",           # alternativas: "SGD", "Adam", "auto"
        lr0=0.001,                   # learning rate inicial
        lrf=0.01,                    # lr final = lr0 * lrf
        momentum=0.937,
        weight_decay=0.0005,
        warmup_epochs=3,

        # --- Data augmentation (importante para texto) ---
        mosaic=1.0,                  # mosaic durante entrenamiento
        close_mosaic=10,             # desactivar mosaic en los últimos 10 epochs
        hsv_h=0.015,                 # poca variación de tono (texto suele ser B/N)
        hsv_s=0.4,
        hsv_v=0.4,
        fliplr=0.0,                  # ⚠ texto: NO flip horizontal (la "p" no es "q")
        flipud=0.0,                  # ⚠ texto: NO flip vertical
        degrees=0.0,                 # texto: poca rotación, o 0 si es texto recto
        translate=0.1,
        scale=0.5,

        # --- Logs y guardado ---
        project="testing",
        name="training",
        exist_ok=True,              # crea carpeta nueva si existe (yolov12_texto2, etc.)
        save=True,
        save_period=-1,              # -1 = solo guarda best.pt y last.pt
        plots=True,                  # genera gráficas de métricas
        verbose=True,
        seed=42,                     # reproducibilidad
    )