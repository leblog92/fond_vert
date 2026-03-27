# camera_manager.py
import cv2
import numpy as np
from PyQt5.QtCore import QThread, pyqtSignal
import logging

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)


class CameraThread(QThread):
    """Thread pour gérer la caméra sans bloquer l'interface"""
    change_pixmap_signal = pyqtSignal(np.ndarray)
    camera_error = pyqtSignal(str)

    def __init__(self):
        super().__init__()
        self.running = False
        self.camera_id = 0
        self.cap = None

    def set_camera(self, camera_id):
        self.camera_id = camera_id

    def run(self):
        self.running = True
        self.cap = cv2.VideoCapture(self.camera_id)

        if not self.cap.isOpened():
            self.camera_error.emit(f"Impossible d'ouvrir la caméra {self.camera_id}")
            return

        self.cap.set(cv2.CAP_PROP_FRAME_WIDTH, 1280)
        self.cap.set(cv2.CAP_PROP_FRAME_HEIGHT, 720)

        while self.running:
            ret, frame = self.cap.read()
            if ret:
                # Pas de flip miroir — la C270 renvoie l'image correctement
                self.change_pixmap_signal.emit(frame)
            else:
                self.camera_error.emit("Erreur de lecture de la caméra")
                break

        # Libération propre de la caméra dans le thread lui-même
        if self.cap:
            self.cap.release()
            self.cap = None

    def stop(self):
        """Demande l'arrêt du thread — ne bloque pas le thread principal."""
        self.running = False
        # Ne pas appeler self.wait() ici : c'est au appelant de le faire
        # si nécessaire, via QThread.wait() avec timeout.


class CameraScanner:
    """Scanner les caméras disponibles"""

    @staticmethod
    def scan_cameras(max_cameras=10):
        available_cameras = []
        for i in range(max_cameras):
            cap = cv2.VideoCapture(i)
            if cap.isOpened():
                ret, _ = cap.read()
                if ret:
                    available_cameras.append({'id': i})
                cap.release()
        return available_cameras