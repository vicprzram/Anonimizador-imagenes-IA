from ultralytics import YOLO
from pathlib import Path

root = Path("ia")

model = YOLO("runs/detect/yolov12_texto-5/weights/best.pt")
resultados = model(root / "images"/ "test"/ "0a730e3b-e27980ec-5e8cd08f-e09488be-ebe3c89e_annotated.png", conf=0.25, imgsz=512)

# Renderizar SIN etiquetas ni scores
img_array = resultados[0].plot(
    labels=False,      # quita el texto "texto"
    conf=False,        # quita el score 0.94
    line_width=2,      # grosor del marco (opcional)
)

# o si estás en notebook:
#from PIL import Image
#Image.fromarray(img_array[..., ::-1]).show()   # BGR→RGB para PIL