# camera_manager.py
import cv2
import numpy as np
from PyQt5.QtCore import QThread, pyqtSignal
import logging
import time

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
        self.target_width = 1280
        self.target_height = 720
        self.use_preview_resolution = False
        
    def set_camera(self, camera_id, use_preview=False):
        self.camera_id = camera_id
        self.use_preview_resolution = use_preview
        
    def run(self):
        self.running = True
        try:
            self.cap = cv2.VideoCapture(self.camera_id, cv2.CAP_DSHOW)
            
            if not self.cap.isOpened():
                self.camera_error.emit(f"Impossible d'ouvrir la caméra {self.camera_id}")
                return
                
            # Lire la résolution réelle de la caméra
            actual_width = int(self.cap.get(cv2.CAP_PROP_FRAME_WIDTH))
            actual_height = int(self.cap.get(cv2.CAP_PROP_FRAME_HEIGHT))
            logger.info(f"Résolution réelle caméra {self.camera_id}: {actual_width}x{actual_height}")
            
            # Essayer de définir la résolution souhaitée
            if actual_width != self.target_width:
                self.cap.set(cv2.CAP_PROP_FRAME_WIDTH, self.target_width)
                self.cap.set(cv2.CAP_PROP_FRAME_HEIGHT, self.target_height)
                time.sleep(0.1)
                
                # Vérifier la résolution après modification
                new_width = int(self.cap.get(cv2.CAP_PROP_FRAME_WIDTH))
                new_height = int(self.cap.get(cv2.CAP_PROP_FRAME_HEIGHT))
                logger.info(f"Résolution après configuration: {new_width}x{new_height}")
            
            logger.info(f"Caméra {self.camera_id} démarrée")
            
            while self.running:
                if self.cap is None:
                    break
                    
                ret, frame = self.cap.read()
                if ret:
                    # Rotation de l'image (miroir)
                    frame = cv2.flip(frame, 1)
                    self.change_pixmap_signal.emit(frame)
                else:
                    logger.warning("Frame vide, tentative de reconnexion...")
                    time.sleep(0.1)
                    
                # Petit délai pour réduire la charge CPU
                time.sleep(0.033)  # ~30 fps max
                
        except Exception as e:
            self.camera_error.emit(f"Erreur caméra: {str(e)}")
            logger.error(f"Erreur dans le thread caméra: {e}")
            
    def stop(self):
        self.running = False
        if self.cap:
            self.cap.release()
            self.cap = None
        self.wait()

class CameraScanner:
    """Scanner les caméras disponibles"""
    
    @staticmethod
    def scan_cameras(max_cameras=5):
        """Scanne les caméras disponibles"""
        available_cameras = []
        cv2.logging.setLogLevel(cv2.logging.LOG_LEVEL_ERROR)
        
        for i in range(max_cameras):
            try:
                cap = cv2.VideoCapture(i, cv2.CAP_DSHOW)
                if cap.isOpened():
                    ret, frame = cap.read()
                    if ret and frame is not None:
                        width = int(cap.get(cv2.CAP_PROP_FRAME_WIDTH))
                        height = int(cap.get(cv2.CAP_PROP_FRAME_HEIGHT))
                        name = f"Caméra {i} ({width}x{height})"
                        available_cameras.append({
                            'id': i,
                            'name': name,
                            'width': width,
                            'height': height
                        })
                        logger.info(f"Caméra trouvée: {name}")
                    cap.release()
            except Exception as e:
                pass
                
        cv2.logging.setLogLevel(cv2.logging.LOG_LEVEL_WARNING)
        return available_cameras