@echo off
title Configuration Camera Iriun
color 0E

echo ========================================
echo    CONFIGURATION CAMERA IRIUN
echo ========================================
echo.

echo Ce script va vous aider a configurer Iriun pour votre tablette Samsung.
echo.

:menu
echo Que souhaitez-vous faire ?
echo.
echo [1] Verifier les cameras disponibles
echo [2] Tester la camera Iriun
echo [3] Afficher les instructions d'installation
echo [4] Quitter
echo.

set /p choix="Votre choix (1-4): "

if "%choix%"=="1" goto check_cameras
if "%choix%"=="2" goto test_camera
if "%choix%"=="3" goto instructions
if "%choix%"=="4" goto fin

echo Choix invalide!
timeout /t 2 >nul
cls
goto menu

:check_cameras
echo.
echo Verification des cameras disponibles...
python -c "
import cv2
print('\nCameras trouvees:')
for i in range(5):
    cap = cv2.VideoCapture(i)
    if cap.isOpened():
        ret, frame = cap.read()
        if ret:
            print(f'  Camera {i}: OK')
        else:
            print(f'  Camera {i}: Detectee mais ne capture pas')
        cap.release()
    else:
        print(f'  Camera {i}: Non disponible')
"
echo.
echo Note: Iriun apparait generalement comme Camera 1 ou 2
pause
cls
goto menu

:test_camera
echo.
set /p cam_index="Entrez l'index de la camera a tester (0-4): "

python -c "
import cv2
import time
cap = cv2.VideoCapture(%cam_index%)
if cap.isOpened():
    print(f'\nCamera %cam_index% ouverte avec succes')
    print('Resolution par defaut:')
    print(f'  Largeur: {int(cap.get(cv2.CAP_PROP_FRAME_WIDTH))}')
    print(f'  Hauteur: {int(cap.get(cv2.CAP_PROP_FRAME_HEIGHT))}')
    print('\nTentative de capture...')
    ret, frame = cap.read()
    if ret:
        print('Capture reussie!')
        print(f'  Dimensions: {frame.shape[1]}x{frame.shape[0]}')
    else:
        print('Echec de la capture')
    cap.release()
else:
    print(f'Impossible d\'ouvrir la camera %cam_index%')
"
pause
cls
goto menu

:instructions
echo.
echo ========== INSTRUCTIONS IRIUN ==========
echo.
echo 1. Sur votre PC:
echo    - Telechargez et installez Iriun depuis: https://iriun.com/
echo    - Redemarrez votre PC apres l'installation
echo.
echo 2. Sur votre tablette Samsung SM-X200:
echo    - Installez Iriun depuis le Google Play Store
echo    - Assurez-vous que la tablette et le PC sont sur le meme WiFi
echo    - Lancez l'application Iriun sur la tablette
echo.
echo 3. Connexion:
echo    - Lancez Iriun sur le PC
echo    - La tablette devrait apparaître automatiquement
echo    - Autorisez la connexion si demande
echo.
echo 4. Dans l'application:
echo    - La camera par defaut utilise l'index 1
echo    - Si probleme, testez avec les indexes 0, 1, ou 2
echo.
echo 5. Resolution recommandee: 1932x2576
echo.
pause
cls
goto menu

:fin
echo.
echo Au revoir!
timeout /t 2 >nul
exit