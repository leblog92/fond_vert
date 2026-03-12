@echo off
title Salon BD - Photomaton
color 0A

:: Configuration
set "REQUIREMENTS_FILE=%~dp0requirements.txt"
set "APP_FILE=%~dp0app.py"
set "CHECK_CAMERA=%~dp0check_camera.py"

:: Masquer la fenêtre de console si désiré (décommentez la ligne suivante)
:: if not "%1"=="hide" start /min cmd /c %0 hide & exit

echo ========================================
echo    SALON BD - PHOTOMATON
echo    Lancement de l'application
echo ========================================
echo.

:: Vérifier si Python est installé
echo [1/4] Verification de l'installation Python...
python --version >nul 2>&1
if %errorlevel% neq 0 (
    echo [ERREUR] Python n'est pas installe ou n'est pas dans le PATH
    echo.
    echo Veuillez installer Python 3.8 ou superieur depuis:
    echo https://www.python.org/downloads/
    echo.
    echo IMPORTANT: Cochez "Add Python to PATH" lors de l'installation
    echo.
    pause
    exit /b 1
)

:: Afficher la version de Python
for /f "tokens=*" %%i in ('python --version 2^>nul') do set "PYTHON_VERSION=%%i"
echo [OK] %PYTHON_VERSION% trouve
echo.

:: Vérifier si pip est disponible
echo [2/4] Verification de pip...
python -m pip --version >nul 2>&1
if %errorlevel% neq 0 (
    echo [INFO] Installation de pip...
    python -m ensurepip --upgrade
)
echo [OK] pip est disponible
echo.

:: Vérifier et installer les requirements
echo [3/4] Verification des dependances...
if exist "%REQUIREMENTS_FILE%" (
    echo Installation des packages requis...
    python -m pip install --upgrade pip >nul 2>&1
    
    :: Lire et installer chaque requirement
    for /f "usebackq tokens=*" %%i in ("%REQUIREMENTS_FILE%") do (
        echo Installation de %%i...
        python -m pip install %%i
        if !errorlevel! neq 0 (
            echo [ERREUR] Impossible d'installer %%i
            echo.
            echo Tentative avec pip directement...
            pip install %%i
        )
    )
) else (
    echo [ATTENTION] Fichier requirements.txt non trouve
    echo Installation des packages standard...
    pip install opencv-python
    pip install Pillow
    pip install numpy
)

echo [OK] Tous les packages sont installes
echo.

:: Vérifier la structure des fichiers
echo [4/4] Verification des fichiers necessaires...
set "MISSING_FILES=0"

:: Vérifier le dossier images
if not exist "%~dp0images" (
    echo [ATTENTION] Dossier 'images' non trouve
    echo Creation du dossier images...
    mkdir "%~dp0images"
    echo.
    echo Veuillez placer vos images dans le dossier 'images' :
    echo - fond1.png, fond2.png, fond3.png
    echo - pp1.png, pp2.png, pp3.png
    echo.
    set "MISSING_FILES=1"
)

:: Vérifier app.py
if not exist "%APP_FILE%" (
    echo [ERREUR] Fichier app.py non trouve
    set "MISSING_FILES=1"
)

:: Vérifier config.json
if not exist "%~dp0config.json" (
    echo [INFO] Creation du fichier config.json par defaut...
    echo { > "%~dp0config.json"
    echo     "camera_settings": { >> "%~dp0config.json"
    echo         "width": 1932, >> "%~dp0config.json"
    echo         "height": 2576, >> "%~dp0config.json"
    echo         "default_device_index": 1 >> "%~dp0config.json"
    echo     }, >> "%~dp0config.json"
    echo     "green_screen": { >> "%~dp0config.json"
    echo         "lower_hue": 35, >> "%~dp0config.json"
    echo         "upper_hue": 85, >> "%~dp0config.json"
    echo         "lower_saturation": 40, >> "%~dp0config.json"
    echo         "upper_saturation": 255, >> "%~dp0config.json"
    echo         "lower_value": 40, >> "%~dp0config.json"
    echo         "upper_value": 255 >> "%~dp0config.json"
    echo     }, >> "%~dp0config.json"
    echo     "matting": { >> "%~dp0config.json"
    echo         "erosion": 1, >> "%~dp0config.json"
    echo         "dilation": 1, >> "%~dp0config.json"
    echo         "blur": 3, >> "%~dp0config.json"
    echo         "edge_threshold": 0.5, >> "%~dp0config.json"
    echo         "matting_strength": 0.3 >> "%~dp0config.json"
    echo     } >> "%~dp0config.json"
    echo } >> "%~dp0config.json"
    echo [OK] Fichier config.json cree
)

if %MISSING_FILES% equ 1 (
    echo.
    echo Certains fichiers sont manquants.
    echo Verifiez la structure avant de continuer.
    pause
)

:: Scanner les caméras disponibles
echo.
echo Scan des cameras disponibles...
python -c "
import cv2
import sys
print('\nCameras trouvees:')
cameras = []
for i in range(5):
    cap = cv2.VideoCapture(i)
    if cap.isOpened():
        ret, frame = cap.read()
        if ret:
            print(f'  Camera {i}: Disponible')
            cameras.append(str(i))
        cap.release()
if not cameras:
    print('  Aucune camera detectee!')
    print('\nVerifiez que:')
    print('  - Iriun est installe et lance')
    print('  - La tablette est connectee au meme WiFi')
    print('  - Les pilotes sont correctement installes')
    sys.exit(1)
" 2>nul

if %errorlevel% neq 0 (
    echo.
    echo [ATTENTION] Probleme de detection de camera
    echo L'application demarrera quand meme, mais verifiez votre configuration.
    echo.
    timeout /t 5 /nobreak >nul
)

:: Options de lancement
echo.
echo ========================================
echo Options de lancement :
echo ========================================
echo.
echo [1] Lancer l'application normalement
echo [2] Lancer avec redimensionnement automatique
echo [3] Lancer en mode diagnostic (avec logs)
echo [4] Quitter
echo.

set /p choice="Votre choix (1-4): "

if "%choice%"=="1" goto launch_normal
if "%choice%"=="2" goto launch_resized
if "%choice%"=="3" goto launch_debug
if "%choice%"=="4" goto quit

echo Choix invalide, lancement normal...
goto launch_normal

:launch_normal
echo.
echo Lancement de l'application...
echo Pour fermer, fermez simplement la fenetre de l'application.
echo.
start "Salon BD" python "%APP_FILE%"
goto wait_and_clean

:launch_resized
echo.
echo Lancement avec redimensionnement automatique...
start "Salon BD" python "%APP_FILE%" --resizable
goto wait_and_clean

:launch_debug
echo.
echo Lancement en mode diagnostic...
echo Les logs seront sauvegardes dans debug.log
echo.
start "Salon BD - Debug" python "%APP_FILE%" --debug > debug.log 2>&1
goto wait_and_clean

:wait_and_clean
echo.
echo L'application est lancee.
echo Cette fenetre peut etre minimisee.
echo.
echo Commandes disponibles :
echo - [Ctrl+C] pour fermer l'application et cette fenetre
echo - Minimisez cette fenetre pour continuer a utiliser l'application
echo.

:wait_loop
timeout /t 2 /nobreak >nul

:: Vérifier si l'application tourne toujours
tasklist /fi "imagename eq python.exe" 2>nul | find /i "python.exe" >nul
if %errorlevel% equ 0 (
    goto wait_loop
) else (
    echo.
    echo Application fermee.
    goto finish
)

:quit
echo.
echo Annulation du lancement.
goto finish

:finish
echo.
echo ========================================
echo Appuyez sur une touche pour fermer...
pause >nul
exit /b 0