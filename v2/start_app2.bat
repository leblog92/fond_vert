@echo off
title Salon BD - Photomaton
color 0A

echo ========================================
echo    SALON BD - PHOTOMATON
echo ========================================
echo.

:: Vérifier Python
python --version >nul 2>&1
if %errorlevel% neq 0 (
    echo Python n'est pas installe!
    echo Veuillez installer Python depuis https://www.python.org/downloads/
    pause
    exit /b 1
)

:: Installer les dépendances si nécessaire
echo Verification des dependances...
pip show opencv-python >nul 2>&1
if %errorlevel% neq 0 (
    echo Installation des packages requis...
    pip install -r requirements.txt
) else (
    echo Dependances deja installees
)

:: Lancer l'application
echo.
echo Lancement de l'application...
start /B python app2.py

echo.
echo L'application est lancee.
echo Fermez cette fenetre pour quitter.
echo.

:: Attendre que l'utilisateur ferme
pause >nul
taskkill /f /im python.exe >nul 2>&1
exit