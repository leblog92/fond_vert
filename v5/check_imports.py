# check_imports.py
import sys
print(f"Python: {sys.version}")
print("-" * 50)

# Vérifier PyQt5
try:
    from PyQt5.QtWidgets import QApplication, QMainWindow
    from PyQt5.QtCore import Qt
    from PyQt5.QtGui import QImage
    print("✓ PyQt5 - OK")
except ImportError as e:
    print(f"✗ PyQt5 - ERREUR: {e}")

# Vérifier OpenCV
try:
    import cv2
    print(f"✓ OpenCV {cv2.__version__} - OK")
except ImportError as e:
    print(f"✗ OpenCV - ERREUR: {e}")

# Vérifier Pillow
try:
    import PIL
    print(f"✓ Pillow {PIL.__version__} - OK")
except ImportError as e:
    print(f"✗ Pillow - ERREUR: {e}")

# Vérifier NumPy
try:
    import numpy as np
    print(f"✓ NumPy {np.__version__} - OK")
except ImportError as e:
    print(f"✗ NumPy - ERREUR: {e}")

# Vérifier piexif
try:
    import piexif
    print(f"✓ piexif - OK")
except ImportError as e:
    print(f"✗ piexif - ERREUR: {e}")

print("-" * 50)
print("Vérification terminée")