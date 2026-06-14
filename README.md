# Anonimizador clínico

Aplicación web que **elimina los datos identificativos sobreimpresos en imágenes
clínicas** (Nombre del paciente, ID, edad, fecha y hora). El usuario sube una
radiografía, la IA localiza el texto, lo reconoce y devuelve la imagen limpia
junto con la lista de lo que ha borrado.

El proceso tiene dos etapas de IA encadenadas:

1. **Detección** — un modelo YOLO (entrenado a medida) localiza las cajas de texto.
2. **Reconocimiento** — PaddleOCR (PP-OCRv5) lee el texto dentro de cada caja.

Después, las zonas de texto se borran reconstruyendo el fondo por *inpainting*,
sin dejar parches de color.

---

## Requisitos previos

- **Python 3.9 – 3.12**
- El modelo YOLO entrenado en `runs/detect/final-trained/weights/best.pt`
  (ver la sección *Modelo* más abajo).
- GPU opcional: acelera mucho la inferencia, pero funciona en CPU.

---

## Instalación

```bash
# 1. Clonar / copiar el proyecto y entrar en la carpeta
git clone https://github.com/vicprzram/Anonimizador-imagenes-IA.git
cd Anonimizador-imagenes-IA

# 2. Crear y activar un entorno virtual
python -m venv venv
source venv/bin/activate        # Windows: venv\Scripts\activate

# 3. Instalar dependencias
pip install -r requirements.txt
```

> **Nota sobre PaddlePaddle:** `requirements.txt` instala la versión **CPU**
> (`paddlepaddle`). Si tienes GPU con CUDA, sustitúyela por `paddlepaddle-gpu`
> con la build que corresponda a tu versión de CUDA.

---

## Ejecución

```bash
python app.py
```

Abre el navegador en **http://localhost:5000** o **http://127.0.0.1:5000**.

Flujo de uso: arrastra o selecciona una imagen → pulsa **Anonimizar** → mientras
procesa verás la animación del obturador → al terminar aparece la comparación
*Original vs Anonimizada*, el texto detectado y un botón para descargar la imagen
limpia.

---

## Estructura del proyecto

```
Anonimizador-imagenes-IA/
├── app.py                    # Servidor Flask (rutas + endpoint de anonimizado)
├── requirements.txt
├── .gitignore
├── static/                   # Frontend (servido por Flask)
│   ├── index.html
│   ├── scripts.js
│   └── styles.css
├── images/                   # Favicons de la web
└── ia/
    ├── ocr_engine.py         # Motor OCR reutilizable (lo usa la app)
    ├── training.py           # Entrenamiento del modelo YOLO
    ├── conf/
    │   └── data.yaml         # Configuración del dataset para YOLO
    ├── images/{train,val,test}/   # Dataset de imágenes
    └── labels_fixed/{train,val}/  # Etiquetas YOLO (cajas de texto)
```

---

## Explicación de cada script `.py`

### `app.py` — Servidor web (Flask)

Es el punto de entrada de la aplicación. Sirve el frontend y expone el endpoint
que hace el trabajo. Sus piezas:

- **Configuración**: carpeta de subidas, extensiones permitidas
  (`png, jpg, jpeg, webp`) y límite de 10 MB por archivo.
- **`extension_permitida(nombre)`**: valida que el archivo subido tenga una
  extensión admitida.
- **`leer_imagen(archivo)`**: convierte el archivo recibido por Flask en una
  imagen de OpenCV (array BGR) **en memoria**, sin escribirla en disco.
- **`png_a_base64(img)`**: codifica una imagen como *data-URL* PNG para poder
  enviarla en el JSON y mostrarla directamente en un `<img>`. Solución para enviar imagenes pesadas sin saturar el servidor.
- **Rutas**:
  - `GET /` → sirve `index.html`.
  - `GET /images/<archivo>` → sirve los favicons.
  - `POST /anonimizar` → recibe la imagen, llama a `procesar_imagen()` del motor
    OCR y devuelve un JSON con: el texto reconocido (`textos` y `lecturas`), las
    cajas detectadas normalizadas (`cajas`, en coordenadas 0–1 para dibujarlas
    sobre la imagen) y la imagen anonimizada en base64 (`imagen`).
- **Manejo de errores**: respuesta clara si el archivo supera el límite (413) o
  si falla la carga de los modelos (500 con mensaje, en vez de romper el servidor).

El import del motor OCR es **diferido** (dentro del endpoint), para que el
servidor arranque rápido y no falle al iniciar si aún no están los modelos.

---

### `ia/ocr_engine.py` — Motor OCR reutilizable

El cerebro del proyecto, aquí todo está encapsulado en funciones y **el modelo se carga una sola vez**, de modo que la app pueda invocarlo en cada petición sin recargarlo.

- **Carga perezosa de modelos** (`_cargar_modelos`): YOLO y PaddleOCR se cargan la   primera vez que se usan, no al importar el módulo. Si faltan los pesos o las
  librerías, guarda el error y permite que la app responda con un mensaje claro.
- **Funciones de preprocesado** que generan varias
  *variantes* de cada recorte para maximizar el acierto del OCR:
  - `_base` / `_unsharp`: reescalado y enfoque básicos.
  - `variantes_normales`: versión normal, con CLAHE+nitidez, e invertida.
  - `variantes_extremas`: para texto casi invisible (blanco sobre blanco):
    estiramiento de contraste, CLAHE agresivo y binarización Otsu.
  - `correccion_iluminacion`: para texto sobre fondo de brillo muy irregular
    (zonas "quemadas" de la radiografía); aplana el gradiente dividiendo por un
    desenfoque grande del fondo.
  - `expandir`: agranda un poco cada caja sin salirse de la imagen.
- **`borrar_texto(img, cajas)`**: el borrado. En lugar de tapar el rectángulo
  entero (lo que dejaría un manchón), construye una **máscara fina solo de los
  trazos del texto** y aplica `cv2.inpaint`, que reconstruye el fondo a partir de
  los píxeles vecinos. Así no quedan parches de color.
- **`procesar_imagen(imagen, borrar_todas=True)`**: la función pública. Recibe una
  ruta o un array, detecta las cajas con YOLO, lee cada una con PaddleOCR probando   todas las variantes y quedándose con la de mayor confianza, borra el texto y devuelve un diccionario con: las `lecturas` fiables (texto, score, caja), la `imagen_anonimizada`, el número de cajas y las cajas normalizadas (`cajas_norm`).
  Con `borrar_todas=True` borra todo lo que YOLO marcó como texto (recomendado para  anonimizar); con `False`, solo lo que el OCR leyó con confianza ≥ 0.5.
- **`modelos_disponibles()`**: comprueba si los modelos se pueden cargar
  (útil para un *health-check*).

---

### `ia/training.py` — Entrenamiento del modelo YOLO

Entrena el detector de texto. Carga un modelo base (`ia/conf/yolo12s.pt`) y lo
entrena con el dataset descrito en `ia/conf/data.yaml`. Los parámetros están
comentados en el propio archivo; los más relevantes:

- `epochs`, `patience`: duración y *early stopping*.
- `imgsz=512`, `batch`: tamaño de entrada y lote (ajustar a la VRAM).
- `device`: `0` para la primera GPU, `"cpu"` si no hay GPU.
- **Data augmentation pensado para texto**: `fliplr=0` y `flipud=0` (no se
  voltea, porque una "p" volteada no es una "q"), poca rotación y poca variación
  de tono.

Genera los pesos en `testing/training/weights/` (según `project`/`name`). Para
que la app los use, colócalos en la ruta `MODELO_PATH` de `ocr_engine.py`.

Ejecución:

```bash
python ia/training.py
```

---

## Notas

- Las carpetas `uploads/`, `ia/deleted/`, los pesos `*.pt` y `runs/` están en
  `.gitignore`: son datos pesados o generados, no van a control de versiones.
- La privacidad depende de dónde despliegues la app: tal cual, procesa las
  imágenes en el servidor donde corre Flask.
