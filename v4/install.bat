@echo off
echo Installation des dépendances pour l'application de montage photo
echo.

echo Mise à jour de pip...
python -m pip install --upgrade pip

echo.
echo Installation des packages...
pip install opencv-python
pip install Pillow
pip install numpy
pip install PyQt5
pip install pyqt5-plugins
pip install piexif

echo.
echo Vérification des installations...
python -c "import cv2; import PIL; import numpy; import PyQt5; import piexif; print('Tous les packages sont installés correctement!')"

echo.
pause