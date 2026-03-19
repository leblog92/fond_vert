# camera_manager.py
import cv2
import numpy as np
from PyQt5.QtCore import QThread, pyqtSignal, QTimer
from PyQt5.QtGui import QImage
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
            
        # Configuration de la résolution
        self.cap.set(cv2.CAP_PROP_FRAME_WIDTH, 1280)
        self.cap.set(cv2.CAP_PROP_FRAME_HEIGHT, 720)
        
        while self.running:
            ret, frame = self.cap.read()
            if ret:
                # Rotation de l'image (miroir)
                frame = cv2.flip(frame, 1)
                self.change_pixmap_signal.emit(frame)
            else:
                self.camera_error.emit("Erreur de lecture de la caméra")
                break
                
    def stop(self):
        self.running = False
        if self.cap:
            self.cap.release()
        self.wait()

class CameraScanner:
    """Scanner les caméras disponibles"""
    
    @staticmethod
    def scan_cameras(max_cameras=10):
        """Scanne les caméras disponibles"""
        available_cameras = []
        
        for i in range(max_cameras):
            cap = cv2.VideoCapture(i)
            if cap.isOpened():
                # Lire quelques informations sur la caméra
                ret, _ = cap.read()
                if ret:
                    width = int(cap.get(cv2.CAP_PROP_FRAME_WIDTH))
                    height = int(cap.get(cv2.CAP_PROP_FRAME_HEIGHT))
                    available_cameras.append({
                        'id': i,
                        'name': f'Caméra {i} ({width}x{height})'
                    })
                cap.release()
                
        return available_cameras