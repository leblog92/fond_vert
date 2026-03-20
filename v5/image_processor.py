# image_processor.py
import cv2
import numpy as np
from PIL import Image
import piexif
from datetime import datetime
import logging
from pathlib import Path
from config import Config

logger = logging.getLogger(__name__)

class GreenScreenProcessor:
    """Traitement d'image pour fond vert"""
    
    def __init__(self):
        # Utiliser des listes Python puis convertir en numpy array
        self.lower_green = np.array([35, 50, 50], dtype=np.uint8)
        self.upper_green = np.array([85, 255, 255], dtype=np.uint8)
        self.smoothness = 5
        self.erode_iterations = 1
        self.dilate_iterations = 2
        
    def update_green_range(self, lower_hue, upper_hue, lower_sat, lower_val):
        """Met à jour la plage de détection du vert"""
        self.lower_green = np.array([lower_hue, lower_sat, lower_val], dtype=np.uint8)
        self.upper_green = np.array([upper_hue, 255, 255], dtype=np.uint8)
        
    def update_morph_params(self, erode, dilate, smooth):
        """Met à jour les paramètres morphologiques"""
        self.erode_iterations = erode
        self.dilate_iterations = dilate
        self.smoothness = smooth
        
    def extract_person(self, frame):
        """Extrait la personne du fond vert"""
        try:
            # Conversion en HSV
            hsv = cv2.cvtColor(frame, cv2.COLOR_BGR2HSV)
            
            # Création du masque pour le fond vert
            mask = cv2.inRange(hsv, self.lower_green, self.upper_green)
            
            # Inversion du masque pour garder la personne
            mask = cv2.bitwise_not(mask)
            
            # Nettoyage du masque
            kernel = np.ones((self.smoothness, self.smoothness), np.uint8)
            mask = cv2.erode(mask, kernel, iterations=self.erode_iterations)
            mask = cv2.dilate(mask, kernel, iterations=self.dilate_iterations)
            
            # Application du masque
            result = cv2.bitwise_and(frame, frame, mask=mask)
            
            # Création d'un fond transparent (RGBA)
            b, g, r = cv2.split(result)
            alpha = mask
            result_rgba = cv2.merge([b, g, r, alpha])
            
            return result_rgba, mask
            
        except Exception as e:
            logger.error(f"Erreur extract_person: {e}")
            return None, None
    
    def load_foreground(self, foreground_path):
        """Charge l'image de premier plan (pp*.png)"""
        try:
            pp_img = cv2.imread(str(foreground_path), cv2.IMREAD_UNCHANGED)
            if pp_img is None:
                raise FileNotFoundError(f"Impossible de charger {foreground_path}")
            
            # Convertir en RGBA si nécessaire
            if pp_img.shape[2] == 3:
                pp_rgba = cv2.cvtColor(pp_img, cv2.COLOR_BGR2BGRA)
            else:
                pp_rgba = pp_img.copy()
                pp_rgba[:, :, 0:3] = cv2.cvtColor(pp_img[:, :, 0:3], cv2.COLOR_BGR2RGB)
                
            return pp_rgba
        except Exception as e:
            logger.error(f"Erreur load_foreground: {e}")
            return None
    
    def composite_image(self, person_rgba, background_path, foreground_path, 
                        position_x, position_y, zone_info, set_config):
        """Composition de l'image finale"""
        
        # Set 0: fond vert uniquement
        if set_config.fond_file == "" or background_path is None or not background_path.exists():
            if person_rgba is not None:
                return person_rgba
            return np.zeros((Config.CAMERA_HEIGHT, Config.CAMERA_WIDTH, 4), dtype=np.uint8)
        
        try:
            # Charger le fond
            background_bgr = cv2.imread(str(background_path))
            if background_bgr is None:
                raise FileNotFoundError(f"Impossible de charger {background_path}")
            
            # Convertir fond en RGB
            background_rgb = cv2.cvtColor(background_bgr, cv2.COLOR_BGR2RGB)
            h_fond, w_fond = background_rgb.shape[:2]
            background_rgba = np.zeros((h_fond, w_fond, 4), dtype=np.uint8)
            background_rgba[:, :, 0:3] = background_rgb
            background_rgba[:, :, 3] = 255
            
            # Charger le premier plan si existe
            foreground_rgba = None
            if foreground_path and foreground_path.exists():
                foreground_rgba = self.load_foreground(foreground_path)
            
            # Redimensionner et positionner la personne
            if person_rgba is not None and person_rgba.size > 0:
                person_height, person_width = person_rgba.shape[:2]
                
                if person_width > 0 and person_height > 0:
                    scale_x = zone_info['largeur'] / person_width
                    scale_y = zone_info['hauteur'] / person_height
                    scale = min(scale_x, scale_y)
                    
                    new_width = max(1, int(person_width * scale))
                    new_height = max(1, int(person_height * scale))
                    
                    person_resized = cv2.resize(person_rgba, (new_width, new_height), 
                                              interpolation=cv2.INTER_LANCZOS4)
                    
                    zone_center_x = set_config.zone_x + zone_info['largeur'] // 2
                    zone_center_y = set_config.zone_y + zone_info['hauteur'] // 2
                    
                    pos_x = zone_center_x - new_width // 2 + position_x
                    pos_y = zone_center_y - new_height // 2 + position_y
                    
                    pos_x = max(0, min(pos_x, w_fond - new_width))
                    pos_y = max(0, min(pos_y, h_fond - new_height))
                    
                    if pos_x < w_fond and pos_y < h_fond and new_width > 0 and new_height > 0:
                        alpha_person = person_resized[:, :, 3] / 255.0
                        for c in range(3):
                            background_rgba[pos_y:pos_y+new_height, pos_x:pos_x+new_width, c] = \
                                (alpha_person * person_resized[:, :, c] + 
                                 (1 - alpha_person) * background_rgba[pos_y:pos_y+new_height, pos_x:pos_x+new_width, c])
            
            # Ajouter le premier plan
            if foreground_rgba is not None and foreground_rgba.size > 0:
                if foreground_rgba.shape[:2] != (h_fond, w_fond):
                    foreground_rgba = cv2.resize(foreground_rgba, (w_fond, h_fond),
                                               interpolation=cv2.INTER_LANCZOS4)
                
                if foreground_rgba.shape[2] == 4:
                    alpha_fore = foreground_rgba[:, :, 3] / 255.0
                    for c in range(3):
                        background_rgba[:, :, c] = (alpha_fore * foreground_rgba[:, :, c] + 
                                                    (1 - alpha_fore) * background_rgba[:, :, c])
            
            return background_rgba
            
        except Exception as e:
            logger.error(f"Erreur composite_image: {e}")
            raise
    
    def create_preview(self, frame, background_path, foreground_path, 
                       position_x, position_y, zone_info, set_config):
        """Crée un aperçu en direct du montage"""
        try:
            if zone_info is None:
                return None
            
            # Redimensionner pour l'aperçu
            preview_frame = cv2.resize(frame, (Config.PREVIEW_WIDTH, Config.PREVIEW_HEIGHT),
                                       interpolation=cv2.INTER_LINEAR)
            
            person_rgba, _ = self.extract_person(preview_frame)
            
            if person_rgba is None:
                return None
            
            # Set 0 ou sans fond
            if set_config.fond_file == "" or background_path is None or not background_path.exists():
                return person_rgba
            
            # Charger et redimensionner le fond
            background_bgr = cv2.imread(str(background_path))
            if background_bgr is None:
                return person_rgba
                
            background_small = cv2.resize(background_bgr, (Config.PREVIEW_WIDTH, Config.PREVIEW_HEIGHT),
                                         interpolation=cv2.INTER_LINEAR)
            background_rgb = cv2.cvtColor(background_small, cv2.COLOR_BGR2RGB)
            background_rgba = np.zeros((Config.PREVIEW_HEIGHT, Config.PREVIEW_WIDTH, 4), dtype=np.uint8)
            background_rgba[:, :, 0:3] = background_rgb
            background_rgba[:, :, 3] = 255
            
            # Positionner la personne (version simplifiée pour aperçu)
            person_height, person_width = person_rgba.shape[:2]
            if person_width > 0 and person_height > 0:
                scale = min(Config.PREVIEW_WIDTH / person_width * 0.5, 
                           Config.PREVIEW_HEIGHT / person_height * 0.5, 1.0)
                new_width = max(1, int(person_width * scale))
                new_height = max(1, int(person_height * scale))
                
                person_resized = cv2.resize(person_rgba, (new_width, new_height),
                                          interpolation=cv2.INTER_LINEAR)
                
                pos_x = (Config.PREVIEW_WIDTH - new_width) // 2 + position_x // 4
                pos_y = (Config.PREVIEW_HEIGHT - new_height) // 2 + position_y // 4
                
                pos_x = max(0, min(pos_x, Config.PREVIEW_WIDTH - new_width))
                pos_y = max(0, min(pos_y, Config.PREVIEW_HEIGHT - new_height))
                
                alpha_person = person_resized[:, :, 3] / 255.0
                for c in range(3):
                    background_rgba[pos_y:pos_y+new_height, pos_x:pos_x+new_width, c] = \
                        (alpha_person * person_resized[:, :, c] + 
                         (1 - alpha_person) * background_rgba[pos_y:pos_y+new_height, pos_x:pos_x+new_width, c])
            
            return background_rgba
            
        except Exception as e:
            logger.error(f"Erreur create_preview: {e}")
            return None
    
    def save_with_metadata(self, image, person_name, email, set_id):
        """Sauvegarde l'image avec métadonnées"""
        timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
        clean_name = "".join(c for c in person_name if c.isalnum() or c in " -_").strip()
        filename = f"salonBD_{clean_name}_{timestamp}_set{set_id}.png"
        filepath = Config.SAVE_DIR / filename
        
        try:
            # Convertir l'image en PIL
            image_pil = Image.fromarray(image)
            
            # Préparer les métadonnées
            exif_dict = {
                "0th": {
                    piexif.ImageIFD.ImageDescription: f"Nom: {person_name} | Email: {email} | Set: {set_id}".encode('utf-8'),
                    piexif.ImageIFD.XPComment: f"Email: {email}".encode('utf-16le'),
                    piexif.ImageIFD.XPAuthor: person_name.encode('utf-16le'),
                    piexif.ImageIFD.XPKeywords: f"salonBD;set{set_id};{person_name}".encode('utf-16le'),
                    piexif.ImageIFD.Artist: person_name.encode('utf-8'),
                },
                "Exif": {
                    piexif.ExifIFD.UserComment: f"Email={email}".encode('utf-8'),
                    piexif.ExifIFD.DateTimeOriginal: datetime.now().strftime("%Y:%m:%d %H:%M:%S").encode('utf-8'),
                }
            }
            
            exif_bytes = piexif.dump(exif_dict)
            image_pil.save(filepath, "PNG", exif=exif_bytes, compress_level=1)
            
            logger.info(f"Image sauvegardée: {filepath}")
            return filepath
            
        except Exception as e:
            logger.error(f"Erreur sauvegarde: {e}")
            raise