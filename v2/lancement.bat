@echo off
title Salon BD - Photomaton
color 0A

echo ========================================
echo    SALON BD - PHOTOMATON
echo    Lancement de l'application
echo ========================================
echo.

:: Définir le chemin du dossier virtuel Python
set "VENV_DIR=%~dp0venv"
set "REQUIREMENTS_FILE=%~dp0requirements.txt"
set "APP_FILE=%~dp0app.py"

:: Vérifier si Python est installé
echo [1/5] Verification de l'installation Python...
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
echo [2/5] Verification de pip...
python -m pip --version >nul 2>&1
if %errorlevel% neq 0 (
    echo [INFO] Installation de pip...
    python -m ensurepip --upgrade
)
echo [OK] pip est disponible
echo.

:: Créer et activer l'environnement virtuel si nécessaire
echo [3/5] Configuration de l'environnement virtuel...
if not exist "%VENV_DIR%" (
    echo Creation de l'environnement virtuel...
    python -m venv "%VENV_DIR%"
    if %errorlevel% neq 0 (
        echo [ERREUR] Impossible de creer l'environnement virtuel
        pause
        exit /b 1
    )
    echo [OK] Environnement virtuel cree
) else (
    echo [OK] Environnement virtuel existant
)

:: Activer l'environnement virtuel
call "%VENV_DIR%\Scripts\activate.bat"

:: Mettre à jour pip dans l'environnement virtuel
echo Mise a jour de pip...
python -m pip install --upgrade pip >nul 2>&1
echo.

:: Vérifier et installer les requirements
echo [4/5] Verification des dependances...
if exist "%REQUIREMENTS_FILE%" (
    echo Installation/Mise a jour des packages requis...
    
    :: Vérifier chaque requirement individuellement
    set "INSTALL_NEEDED=0"
    
    :: Lire le fichier requirements.txt et vérifier chaque package
    for /f "usebackq tokens=*" %%i in ("%REQUIREMENTS_FILE%") do (
        python -c "import pkg_resources; pkg_resources.require('%%i')" 2>nul
        if !errorlevel! neq 0 (
            echo [INSTALL] Installation de %%i...
            python -m pip install %%i
            if !errorlevel! neq 0 (
                echo [ERREUR] Impossible d'installer %%i
                pause
                exit /b 1
            )
        ) else (
            echo [OK] %%i est deja installe
        )
    )
    echo [OK] Toutes les dependances sont installees
) else (
    echo [ATTENTION] Fichier requirements.txt non trouve
    echo Installation des dependances standard...
    python -m pip install opencv-python==4.8.1.78
    python -m pip install Pillow==10.1.0
    python -m pip install numpy==1.24.3
)
echo.

:: Vérifier que le dossier images existe
echo [5/5] Verification de la structure des fichiers...
if not exist "%~dp0images" (
    echo [ATTENTION] Dossier 'images' non trouve
    echo Creation du dossier images...
    mkdir "%~dp0images"
    echo.
    echo Veuillez placer vos images dans le dossier 'images' :
    echo - fond1.png, fond2.png, fond3.png
    echo - pp1.png, pp2.png, pp3.png
    echo.
    pause
)

:: Vérifier la présence des fichiers principaux
set "MISSING_FILES=0"
if not exist "%APP_FILE%" (
    echo [ERREUR] Fichier app.py non trouve
    set "MISSING_FILES=1"
)

if %MISSING_FILES% equ 1 (
    echo.
    echo Certains fichiers essentiels sont manquants.
    echo Assurez-vous que tous les fichiers Python sont presents.
    pause
    exit /b 1
)

echo [OK] Structure des fichiers validee
echo.

:: Lancer l'application
echo ========================================
echo Lancement de l'application...
echo ========================================
echo.

:: Vérifier la caméra avant de lancer
echo Verification rapide de la camera...
python -c "import cv2; cap=cv2.VideoCapture(1); print('Camera OK' if cap.isOpened() else 'Camera non disponible'); cap.release()" 2>nul

echo.
echo L'application va demarrer...
echo Si la camera ne fonctionne pas, fermez l'application et lancez check_camera.py
echo.
timeout /t 3 /nobreak >nul

:: Lancer l'application Python
start "Salon BD - Application" /B python "%APP_FILE%"

:: Attendre que l'application se ferme
echo.
echo Appuyez sur Ctrl+C dans cette fenetre pour fermer l'application
echo (ou fermez simplement la fenetre graphique)
echo.

:: Garder la fenêtre ouverte
:boucle
timeout /t 1 /nobreak >nul
tasklist /fi "imagename eq python.exe" 2>nul | find /i "python.exe" >nul
if %errorlevel% equ 0 (
    goto boucle
)

:: Nettoyage à la fermeture
echo.
echo ========================================
echo Application fermee. Nettoyage...
echo ========================================

:: Désactiver l'environnement virtuel
call "%VENV_DIR%\Scripts\deactivate.bat" >nul 2>&1

echo.
echo Appuyez sur une touche pour fermer cette fenetre
pause >nul
exit /b 0