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
        hsv = cv2.cvtColor(frame, cv2.COLOR_BGR2HSV)
        mask = cv2.inRange(hsv, self.lower_green, self.upper_green)
        mask = cv2.bitwise_not(mask)
        kernel = np.ones((self.smoothness, self.smoothness), np.uint8)
        mask = cv2.erode(mask, kernel, iterations=self.erode_iterations)
        mask = cv2.dilate(mask, kernel, iterations=self.dilate_iterations)
        result = cv2.bitwise_and(frame, frame, mask=mask)
        b, g, r = cv2.split(result)
        alpha = mask
        result_rgba = cv2.merge([b, g, r, alpha])
        return result_rgba, mask
    
    def load_foreground(self, foreground_path):
        """Charge l'image de premier plan (pp*.png)"""
        pp_img = cv2.imread(str(foreground_path), cv2.IMREAD_UNCHANGED)
        if pp_img is None:
            raise FileNotFoundError(f"Impossible de charger {foreground_path}")
        if pp_img.shape[2] == 3:
            pp_rgba = cv2.cvtColor(pp_img, cv2.COLOR_BGR2BGRA)
        else:
            pp_rgba = pp_img.copy()
            pp_rgba[:, :, 0:3] = cv2.cvtColor(pp_img[:, :, 0:3], cv2.COLOR_BGR2RGB)
        return pp_rgba
    
    def composite_image(self, person_rgba, background_path, foreground_path, 
                    position_x, position_y, zone_info, set_config):
        """Composition de l'image finale avec respect des dimensions du fond"""
        
        if zone_info is None:
            raise ValueError("zone_info ne peut pas être None")
        
        background_bgr = cv2.imread(str(background_path))
        if background_bgr is None:
            raise FileNotFoundError(f"Impossible de charger {background_path}")
        
        background_rgb = cv2.cvtColor(background_bgr, cv2.COLOR_BGR2RGB)
        h_fond, w_fond = background_rgb.shape[:2]
        background_rgba = np.zeros((h_fond, w_fond, 4), dtype=np.uint8)
        background_rgba[:, :, 0:3] = background_rgb
        background_rgba[:, :, 3] = 255
        
        logger.info(f"Dimensions du fond: {w_fond}x{h_fond}")
        
        foreground_rgba = self.load_foreground(foreground_path)
        
        if person_rgba is not None and person_rgba.size > 0:
            person_height, person_width = person_rgba.shape[:2]
            
            if person_width > 0 and person_height > 0:
                scale_x = zone_info['largeur'] / person_width
                scale_y = zone_info['hauteur'] / person_height
                scale = min(scale_x, scale_y)
                
                new_width = int(person_width * scale)
                new_height = int(person_height * scale)
                
                logger.info(f"Personne redimensionnée: {new_width}x{new_height} (scale: {scale:.2f})")
                
                if new_width > 0 and new_height > 0:
                    person_resized = cv2.resize(person_rgba, (new_width, new_height), 
                                              interpolation=cv2.INTER_LANCZOS4)
                else:
                    person_resized = person_rgba
                
                zone_center_x = set_config.zone_x + zone_info['largeur'] // 2
                zone_center_y = set_config.zone_y + zone_info['hauteur'] // 2
                
                pos_x = zone_center_x - new_width // 2 + position_x
                pos_y = zone_center_y - new_height // 2 + position_y
                
                pos_x = max(0, min(pos_x, w_fond - new_width))
                pos_y = max(0, min(pos_y, h_fond - new_height))
                
                logger.info(f"Position personne: ({pos_x}, {pos_y})")
                
                if new_width > 0 and new_height > 0:
                    alpha_person = person_resized[:, :, 3] / 255.0
                    for c in range(3):
                        if pos_y + new_height <= h_fond and pos_x + new_width <= w_fond:
                            roi = background_rgba[pos_y:pos_y+new_height, pos_x:pos_x+new_width, c]
                            background_rgba[pos_y:pos_y+new_height, pos_x:pos_x+new_width, c] = \
                                (alpha_person * person_resized[:, :, c] + 
                                 (1 - alpha_person) * roi)
        
        if foreground_rgba is not None and foreground_rgba.size > 0:
            if foreground_rgba.shape[:2] != (h_fond, w_fond):
                logger.info(f"Redimensionnement du premier plan de {foreground_rgba.shape[:2]} à {h_fond}x{w_fond}")
                foreground_rgba = cv2.resize(foreground_rgba, (w_fond, h_fond),
                                           interpolation=cv2.INTER_LANCZOS4)
            if foreground_rgba.shape[2] == 4:
                alpha_fore = foreground_rgba[:, :, 3] / 255.0
                for c in range(3):
                    background_rgba[:, :, c] = (alpha_fore * foreground_rgba[:, :, c] + 
                                                (1 - alpha_fore) * background_rgba[:, :, c])
                background_rgba[:, :, 3] = np.maximum(background_rgba[:, :, 3], 
                                                      foreground_rgba[:, :, 3])
        
        return background_rgba
    
    def create_preview(self, frame, background_path, foreground_path, 
                       position_x, position_y, zone_info, set_config):
        """Crée un aperçu en direct du montage (redimensionné pour l'affichage)"""
        try:
            if zone_info is None:
                logger.error("zone_info est None dans create_preview")
                return None
            if set_config is None:
                logger.error("set_config est None dans create_preview")
                return None
                
            person_rgba, _ = self.extract_person(frame)
            
            if person_rgba is None:
                logger.error("person_rgba est None")
                return None
            
            full_image = self.composite_image(person_rgba, background_path, foreground_path,
                                             position_x, position_y, zone_info, set_config)
            
            if full_image is not None:
                h, w = full_image.shape[:2]
                if h > 0 and w > 0:
                    display_height = 450
                    display_width = int(w * display_height / h)
                    preview_small = cv2.resize(full_image, (display_width, display_height), 
                                              interpolation=cv2.INTER_AREA)
                    # Correction bug couleurs : BGRA → RGB pour affichage Qt
                    preview_rgb = cv2.cvtColor(preview_small, cv2.COLOR_BGRA2RGB)
                    return preview_rgb
            return None
                
        except Exception as e:
            logger.error(f"Erreur lors de la création de l'aperçu: {e}")
            import traceback
            traceback.print_exc()
            return None

    def save_with_metadata(self, image, person_name, email, set_id):
        """Sauvegarde l'image en JPEG avec métadonnées visibles dans Windows"""
        timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
        clean_name = "".join(c for c in person_name if c.isalnum() or c in " -_").strip()
        filename = f"salonBD_{clean_name}_{timestamp}_set{set_id}.jpg"
        filepath = Config.SAVE_DIR / filename

        # Convertir RGBA → RGB (JPEG ne supporte pas la transparence)
        image_rgb = cv2.cvtColor(image, cv2.COLOR_BGRA2RGB)
        image_pil = Image.fromarray(image_rgb)

        # Préparer les métadonnées EXIF
        exif_dict = {
            "0th": {
                piexif.ImageIFD.ImageDescription: f"Nom: {person_name} | Email: {email} | Set: {set_id}".encode('utf-8'),
                piexif.ImageIFD.XPComment: f"Email: {email}".encode('utf-16le'),
                piexif.ImageIFD.XPAuthor: person_name.encode('utf-16le'),
                piexif.ImageIFD.XPKeywords: f"salonBD;set{set_id};{person_name}".encode('utf-16le'),
                piexif.ImageIFD.XPSubject: f"Photo {person_name}".encode('utf-16le'),
                piexif.ImageIFD.Artist: person_name.encode('utf-8'),
                piexif.ImageIFD.Copyright: f"© {person_name}".encode('utf-8'),
            },
            "Exif": {
                piexif.ExifIFD.UserComment: f"Email={email}".encode('utf-8'),
                piexif.ExifIFD.DateTimeOriginal: datetime.now().strftime("%Y:%m:%d %H:%M:%S").encode('utf-8'),
            },
            "GPS": {}
        }
        exif_bytes = piexif.dump(exif_dict)

        # Sauvegarder en JPEG qualité 85
        image_pil.save(filepath, "JPEG", quality=85, optimize=True, exif=exif_bytes)

        # Fichier texte associé
        txt_filepath = filepath.with_suffix('.txt')
        with open(txt_filepath, 'w', encoding='utf-8') as f:
            f.write(f"Nom: {person_name}\n")
            f.write(f"Email: {email}\n")
            f.write(f"Set: {set_id}\n")
            f.write(f"Date: {timestamp}\n")

        logger.info(f"Image sauvegardée: {filepath}")
        logger.info(f"Fichier métadonnées: {txt_filepath}")

        return filepath