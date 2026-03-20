@echo off
echo ========================================
echo Installation pour Python 3.13.7
echo ========================================
echo.

echo Mise à jour de pip, setuptools et wheel...
python -m pip install --upgrade pip setuptools wheel

echo.
echo Installation de numpy 2.1.3 (compatible Python 3.13)...
python -m pip install numpy==2.1.3

echo.
echo Installation de opencv-python...
python -m pip install opencv-python==4.10.0.84

echo.
echo Installation de PyQt5...
python -m pip install PyQt5==5.15.11

echo.
echo Installation de Pillow...
python -m pip install Pillow==11.0.0

echo.
echo Installation de piexif...
python -m pip install piexif==1.1.3

echo.
echo ========================================
echo Vérification des installations
echo ========================================
python -c "import numpy; print('NumPy:', numpy.__version__)"
python -c "import cv2; print('OpenCV:', cv2.__version__)"
python -c "import PyQt5; print('PyQt5:', PyQt5.QtCore.PYQT_VERSION_STR)"
python -c "import PIL; print('Pillow:', PIL.__version__)"
python -c "import piexif; print('piexif: installé')"

echo.
echo Installation terminée !
pause