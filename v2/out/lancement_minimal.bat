@echo off
title Salon BD
color 0A

echo Salon BD - Photomaton
echo =====================
echo.

:: Vérifier Python
python --version >nul 2>&1
if %errorlevel% neq 0 (
    echo Python n'est pas installe!
    pause
    exit /b 1
)

:: Installer les dépendances si nécessaire
echo Verification des dependances...
pip install -r requirements.txt 2>nul
if %errorlevel% neq 0 (
    echo Installation des packages...
    pip install opencv-python Pillow numpy
)

:: Lancer l'application
echo.
echo Lancement de l'application...
start python app.py

echo.
echo Application lancee !
echo Fermez cette fenetre pour quitter.
pause >nul

:: Nettoyer les processus Python si nécessaire
taskkill /f /im python.exe 2>nul
exit