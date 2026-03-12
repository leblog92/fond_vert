@echo off
title Diagnostic Salon BD
color 0E

echo ========================================
echo DIAGNOSTIC SALON BD
echo ========================================
echo.

:: 1. Vérifier Python
echo [1/5] Python :
python --version 2>&1
if %errorlevel% neq 0 (echo [ERREUR] Python non trouve) else (echo [OK])
echo.

:: 2. Vérifier pip
echo [2/5] Pip :
pip --version 2>&1 | find "python"
if %errorlevel% neq 0 (echo [ERREUR] Pip non trouve) else (echo [OK])
echo.

:: 3. Vérifier les packages
echo [3/5] Packages Python :
python -c "import cv2; print('OpenCV:', cv2.__version__)" 2>nul || echo [MANQUANT] OpenCV
python -c "import PIL; print('Pillow:', PIL.__version__)" 2>nul || echo [MANQUANT] Pillow
python -c "import numpy; print('NumPy:', numpy.__version__)" 2>nul || echo [MANQUANT] NumPy
echo.

:: 4. Vérifier les caméras
echo [4/5] Cameras :
python -c "
import cv2
for i in range(5):
    cap = cv2.VideoCapture(i)
    if cap.isOpened():
        print(f'Camera {i}: OK')
        cap.release()
" 2>nul
echo.

:: 5. Vérifier les fichiers
echo [5/5] Fichiers projet :
if exist app.py (echo app.py: OK) else (echo app.py: MANQUANT)
if exist config.json (echo config.json: OK) else (echo config.json: MANQUANT)
if exist images\fond1.png (echo images\fond1.png: OK) else (echo images\fond1.png: MANQUANT)
echo.

echo ========================================
echo Diagnostic termine.
pause