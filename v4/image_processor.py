# image_processor.py
import cv2
import numpy as np
from PIL import Image, ImageOps
import piexif
from datetime import datetime
import logging
from pathlib import Path
from config import Config

logger = logging.getLogger(__name__)

class GreenScreenProcessor:
    """Traitement d'image pour fond vert"""
    
    def __init__(self):
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
    
    def load_foreground(self, foreground_path):
        """Charge l'image de premier plan (pp*.png)"""
        pp_img = cv2.imread(str(foreground_path), cv2.IMREAD_UNCHANGED)
        if pp_img is None:
            raise FileNotFoundError(f"Impossible de charger {foreground_path}")
        
        # Convertir en RGBA si nécessaire
        if pp_img.shape[2] == 3:
            pp_rgba = cv2.cvtColor(pp_img, cv2.COLOR_BGR2BGRA)
        else:
            pp_rgba = pp_img
            
        return pp_rgba
    
    def composite_image(self, person_rgba, background_path, foreground_path, 
                        position_x, position_y, zone_info, set_config):
        """Composition de l'image finale avec fond et premier plan"""
        
        # 1. Charger le fond
        background_bgr = cv2.imread(str(background_path))
        if background_bgr is None:
            raise FileNotFoundError(f"Impossible de charger {background_path}")
            
        background_rgb = cv2.cvtColor(background_bgr, cv2.COLOR_BGR2RGB)
        
        # Convertir en RGBA
        if background_rgb.shape[2] == 3:
            background_rgba = cv2.cvtColor(background_rgb, cv2.COLOR_RGB2RGBA)
        else:
            background_rgba = background_rgb.copy()
        
        # 2. Charger le premier plan
        foreground = self.load_foreground(foreground_path)
        
        # 3. Redimensionner et positionner la personne
        person_height, person_width = person_rgba.shape[:2]
        
        # Calculer le facteur d'échelle pour adapter à la zone
        scale_x = zone_info['largeur'] / person_width if person_width > 0 else 1
        scale_y = zone_info['hauteur'] / person_height if person_height > 0 else 1
        scale = min(scale_x, scale_y)
        
        new_width = int(person_width * scale)
        new_height = int(person_height * scale)
        
        # Redimensionner la personne
        if new_width > 0 and new_height > 0:
            person_resized = cv2.resize(person_rgba, (new_width, new_height), 
                                        interpolation=cv2.INTER_LANCZOS4)
        else:
            person_resized = person_rgba
        
        # Position dans la zone
        zone_center_x = set_config.zone_x + zone_info['largeur'] // 2
        zone_center_y = set_config.zone_y + zone_info['hauteur'] // 2
        
        # Position finale avec ajustements
        pos_x = zone_center_x - new_width // 2 + position_x
        pos_y = zone_center_y - new_height // 2 + position_y
        
        # S'assurer que la personne reste dans l'image
        pos_x = max(0, min(pos_x, background_rgba.shape[1] - new_width))
        pos_y = max(0, min(pos_y, background_rgba.shape[0] - new_height))
        
        # 4. Composition - d'abord la personne sur le fond
        if new_width > 0 and new_height > 0:
            alpha_person = person_resized[:, :, 3] / 255.0
            alpha_background = 1.0 - alpha_person
            
            for c in range(3):
                background_rgba[pos_y:pos_y+new_height, pos_x:pos_x+new_width, c] = \
                    (alpha_person * person_resized[:, :, c] + 
                     alpha_background * background_rgba[pos_y:pos_y+new_height, 
                                                        pos_x:pos_x+new_width, c])
        
        # 5. Ajouter le premier plan (par-dessus)
        # Redimensionner le premier plan à la taille du fond si nécessaire
        if foreground.shape[:2] != background_rgba.shape[:2]:
            foreground = cv2.resize(foreground, 
                                   (background_rgba.shape[1], background_rgba.shape[0]),
                                   interpolation=cv2.INTER_LANCZOS4)
        
        # Composition avec le premier plan (qui a son propre canal alpha)
        if foreground.shape[2] == 4:
            alpha_fore = foreground[:, :, 3] / 255.0
            alpha_bg = 1.0 - alpha_fore
            
            for c in range(3):
                background_rgba[:, :, c] = (alpha_fore * foreground[:, :, c] + 
                                            alpha_bg * background_rgba[:, :, c])
        
        return background_rgba
    
    def create_preview(self, frame, background_path, foreground_path, 
                       position_x, position_y, zone_info, set_config):
        """Crée un aperçu en direct du montage"""
        try:
            # Extraire la personne
            person_rgba, _ = self.extract_person(frame)
            
            # Composer l'image
            preview = self.composite_image(person_rgba, background_path, foreground_path,
                                         position_x, position_y, zone_info, set_config)
            
            # Redimensionner pour l'affichage (plus petit)
            preview_small = cv2.resize(preview, (640, 360), interpolation=cv2.INTER_AREA)
            
            return preview_small
            
        except Exception as e:
            logger.error(f"Erreur lors de la création de l'aperçu: {e}")
            return None
    
    def save_with_metadata(self, image, person_name, email, set_id):
        """Sauvegarde l'image avec métadonnées"""
        # Générer le nom du fichier
        timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
        # Nettoyer le nom de la personne (enlever les caractères problématiques)
        clean_name = "".join(c for c in person_name if c.isalnum() or c in " -_").strip()
        filename = f"salonBD_{clean_name}_{timestamp}_set{set_id}.png"
        filepath = Config.SAVE_DIR / filename
        
        # Convertir l'image en PIL
        image_pil = Image.fromarray(image)
        
        # Préparer les métadonnées EXIF
        exif_dict = {
            "0th": {
                piexif.ImageIFD.ImageDescription: f"Personne: {person_name}, Email: {email}".encode('utf-8'),
                piexif.ImageIFD.XPComment: f"Set {set_id}".encode('utf-16le')
            },
            "Exif": {
                piexif.ExifIFD.UserComment: f"Email={email}".encode('utf-8')
            }
        }
        
        exif_bytes = piexif.dump(exif_dict)
        
        # Sauvegarder
        image_pil.save(filepath, "PNG", exif=exif_bytes)
        logger.info(f"Image sauvegardée: {filepath}")
        
        return filepath