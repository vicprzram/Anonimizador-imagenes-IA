import cv2, numpy as np
recorte = img[ey1:ey2, ex1:ex2]   # la caja problemática
gris = cv2.cvtColor(recorte, cv2.COLOR_BGR2GRAY)
print("min:", gris.min(), "max:", gris.max(), "valores únicos:", len(np.unique(gris)))