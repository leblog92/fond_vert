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
        self.lower_green = np.array([lower_hue, lower_sat, lower_val], dtype=np.uint8)
        self.upper_green = np.array([upper_hue, 255, 255], dtype=np.uint8)

    def update_morph_params(self, erode, dilate, smooth):
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
        result_rgba = cv2.merge([b, g, r, mask])
        return result_rgba, mask

    def load_foreground(self, foreground_path):
        """Charge l'image de premier plan"""
        pp_img = cv2.imread(str(foreground_path), cv2.IMREAD_UNCHANGED)
        if pp_img is None:
            raise FileNotFoundError(f"Impossible de charger {foreground_path}")
        if pp_img.shape[2] == 3:
            pp_rgba = cv2.cvtColor(pp_img, cv2.COLOR_BGR2BGRA)
        else:
            pp_rgba = pp_img.copy()
            pp_rgba[:, :, 0:3] = cv2.cvtColor(pp_img[:, :, 0:3], cv2.COLOR_BGR2RGB)
        return pp_rgba

    def _composite(self, person_rgba, background_bgr, foreground_rgba,
                   position_x, position_y,
                   zone_largeur, zone_hauteur, zone_x, zone_y):
        """
        Composition générique fond + personne + premier plan.
        Travaille aux dimensions exactes du background_bgr fourni.
        Retourne un tableau BGRA.
        """
        background_rgb = cv2.cvtColor(background_bgr, cv2.COLOR_BGR2RGB)
        h_fond, w_fond = background_rgb.shape[:2]

        canvas = np.zeros((h_fond, w_fond, 4), dtype=np.uint8)
        canvas[:, :, 0:3] = background_rgb
        canvas[:, :, 3] = 255

        # Positionner la personne
        if person_rgba is not None and person_rgba.size > 0:
            ph, pw = person_rgba.shape[:2]
            if pw > 0 and ph > 0:
                scale = min(zone_largeur / pw, zone_hauteur / ph)
                nw = max(1, int(pw * scale))
                nh = max(1, int(ph * scale))
                person_resized = cv2.resize(person_rgba, (nw, nh),
                                            interpolation=cv2.INTER_LANCZOS4)
                zone_cx = zone_x + zone_largeur // 2
                zone_cy = zone_y + zone_hauteur // 2
                px = max(0, min(zone_cx - nw // 2 + position_x, w_fond - nw))
                py = max(0, min(zone_cy - nh // 2 + position_y, h_fond - nh))
                if px + nw <= w_fond and py + nh <= h_fond:
                    alpha_p = person_resized[:, :, 3] / 255.0
                    for c in range(3):
                        roi = canvas[py:py+nh, px:px+nw, c]
                        canvas[py:py+nh, px:px+nw, c] = (
                            alpha_p * person_resized[:, :, c] + (1 - alpha_p) * roi
                        )

        # Ajouter le premier plan
        if foreground_rgba is not None and foreground_rgba.size > 0:
            if foreground_rgba.shape[:2] != (h_fond, w_fond):
                foreground_rgba = cv2.resize(foreground_rgba, (w_fond, h_fond),
                                             interpolation=cv2.INTER_LANCZOS4)
            if foreground_rgba.shape[2] == 4:
                alpha_f = foreground_rgba[:, :, 3] / 255.0
                for c in range(3):
                    canvas[:, :, c] = (alpha_f * foreground_rgba[:, :, c] +
                                       (1 - alpha_f) * canvas[:, :, c])
                canvas[:, :, 3] = np.maximum(canvas[:, :, 3], foreground_rgba[:, :, 3])

        return canvas

    def composite_image(self, person_rgba, background_path, foreground_path,
                        position_x, position_y, zone_info, set_config):
        """
        Composition finale en pleine résolution (montage sauvegardé).
        Utilise fond*.jpg + pp*.png (2000px).
        """
        if zone_info is None:
            raise ValueError("zone_info ne peut pas être None")

        background_bgr = cv2.imread(str(background_path))
        if background_bgr is None:
            raise FileNotFoundError(f"Impossible de charger {background_path}")

        foreground_rgba = self.load_foreground(foreground_path)

        return self._composite(
            person_rgba, background_bgr, foreground_rgba,
            position_x, position_y,
            zone_info['largeur'], zone_info['hauteur'],
            zone_info['x'], zone_info['y']
        )

    def create_preview(self, frame, ui_background_bgr, ui_foreground_rgba,
                       position_x, position_y, set_config):
        """
        Aperçu en direct utilisant les images UI déjà en cache (600px).
        position_x/y (valeurs slider) sont mis à l'échelle UI avant composition.
        """
        try:
            if ui_background_bgr is None or ui_foreground_rgba is None:
                return None

            person_rgba, _ = self.extract_person(frame)
            if person_rgba is None:
                return None

            # Adapter le décalage de position à l'échelle UI
            ui_pos_x = int(position_x * Config.UI_SCALE)
            ui_pos_y = int(position_y * Config.UI_SCALE)

            result = self._composite(
                person_rgba, ui_background_bgr, ui_foreground_rgba,
                ui_pos_x, ui_pos_y,
                set_config.ui_zone_largeur, set_config.ui_zone_hauteur,
                set_config.ui_zone_x, set_config.ui_zone_y
            )

            # BGRA → RGB pour affichage Qt
            return cv2.cvtColor(result, cv2.COLOR_BGRA2RGB)

        except Exception as e:
            logger.error(f"Erreur create_preview: {e}")
            import traceback
            traceback.print_exc()
            return None

    def save_with_metadata(self, image, person_name, email, set_id):
        """Sauvegarde l'image en JPEG avec métadonnées visibles dans Windows"""
        timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
        clean_name = "".join(c for c in person_name if c.isalnum() or c in " -_").strip()
        filename = f"salonBD_{clean_name}_{timestamp}_set{set_id}.jpg"
        filepath = Config.SAVE_DIR / filename

        # BGRA → RGB (JPEG ne supporte pas la transparence)
        image_rgb = cv2.cvtColor(image, cv2.COLOR_BGRA2RGB)
        image_pil = Image.fromarray(image_rgb)

        exif_dict = {
            "0th": {
                piexif.ImageIFD.ImageDescription: f"Nom: {person_name} | Email: {email} | Set: {set_id}".encode('utf-8'),
                piexif.ImageIFD.XPComment:  f"Email: {email}".encode('utf-16le'),
                piexif.ImageIFD.XPAuthor:   person_name.encode('utf-16le'),
                piexif.ImageIFD.XPKeywords: f"salonBD;set{set_id};{person_name}".encode('utf-16le'),
                piexif.ImageIFD.XPSubject:  f"Photo {person_name}".encode('utf-16le'),
                piexif.ImageIFD.Artist:     person_name.encode('utf-8'),
                piexif.ImageIFD.Copyright:  f"© {person_name}".encode('utf-8'),
            },
            "Exif": {
                piexif.ExifIFD.UserComment:      f"Email={email}".encode('utf-8'),
                piexif.ExifIFD.DateTimeOriginal: datetime.now().strftime("%Y:%m:%d %H:%M:%S").encode('utf-8'),
            },
            "GPS": {}
        }
        exif_bytes = piexif.dump(exif_dict)
        image_pil.save(filepath, "JPEG", quality=85, optimize=True, exif=exif_bytes)

        txt_filepath = filepath.with_suffix('.txt')
        with open(txt_filepath, 'w', encoding='utf-8') as f:
            f.write(f"Nom: {person_name}\n")
            f.write(f"Email: {email}\n")
            f.write(f"Set: {set_id}\n")
            f.write(f"Date: {timestamp}\n")

        logger.info(f"Image sauvegardée: {filepath}")
        return filepath
