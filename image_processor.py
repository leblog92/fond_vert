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
        """Extrait la personne du fond vert — retourne BGRA (ordre natif OpenCV)"""
        hsv = cv2.cvtColor(frame, cv2.COLOR_BGR2HSV)
        mask = cv2.inRange(hsv, self.lower_green, self.upper_green)
        mask = cv2.bitwise_not(mask)
        kernel = np.ones((self.smoothness, self.smoothness), np.uint8)
        mask = cv2.erode(mask, kernel, iterations=self.erode_iterations)
        mask = cv2.dilate(mask, kernel, iterations=self.dilate_iterations)
        result = cv2.bitwise_and(frame, frame, mask=mask)
        b, g, r = cv2.split(result)
        result_bgra = cv2.merge([b, g, r, mask])  # ordre BGR natif OpenCV
        return result_bgra, mask

    def load_foreground(self, foreground_path):
        """Charge le premier plan en BGRA (ordre natif OpenCV)"""
        pp_img = cv2.imread(str(foreground_path), cv2.IMREAD_UNCHANGED)
        if pp_img is None:
            raise FileNotFoundError(f"Impossible de charger {foreground_path}")
        if pp_img.shape[2] == 3:
            pp_bgra = cv2.cvtColor(pp_img, cv2.COLOR_BGR2BGRA)
        else:
            pp_bgra = pp_img.copy()   # déjà BGRA — pas de conversion
        return pp_bgra

    def _blend_onto(self, canvas, layer, alpha, px, py, nw, nh):
        """
        Compose 'layer' sur 'canvas' à la position (px, py).
        Gère le clipping : si layer dépasse canvas, seule la partie visible est composée.
        canvas et layer sont en ordre BGR/BGRA natif OpenCV.
        alpha : tableau 2D float32 de forme (nh, nw).
        """
        h_c, w_c = canvas.shape[:2]

        # Calcul de la zone visible dans le canvas
        x0_c = max(px, 0)
        y0_c = max(py, 0)
        x1_c = min(px + nw, w_c)
        y1_c = min(py + nh, h_c)

        if x0_c >= x1_c or y0_c >= y1_c:
            return  # complètement hors canvas

        # Zone correspondante dans layer / alpha
        x0_l = x0_c - px
        y0_l = y0_c - py
        x1_l = x0_l + (x1_c - x0_c)
        y1_l = y0_l + (y1_c - y0_c)

        a = alpha[y0_l:y1_l, x0_l:x1_l, np.newaxis]  # (h, w, 1)
        src = layer[y0_l:y1_l, x0_l:x1_l, :3].astype(np.float32)
        dst = canvas[y0_c:y1_c, x0_c:x1_c, :3].astype(np.float32)

        canvas[y0_c:y1_c, x0_c:x1_c, :3] = np.clip(
            a * src + (1 - a) * dst, 0, 255
        ).astype(np.uint8)

    def _composite(self, person_bgra, background_bgr, foreground_bgra,
                   position_x, position_y, scale_z,
                   zone_largeur, zone_hauteur, zone_x, zone_y):
        """
        Composition générique fond + personne + premier plan.
        Tout reste en BGR/BGRA natif OpenCV — pas de conversion de canaux.
        Retourne un tableau BGRA.
        """
        h_fond, w_fond = background_bgr.shape[:2]

        # Canvas BGRA initialisé avec le fond
        canvas = np.zeros((h_fond, w_fond, 4), dtype=np.uint8)
        canvas[:, :, :3] = background_bgr
        canvas[:, :, 3] = 255

        # --- Personne ---
        if person_bgra is not None and person_bgra.size > 0:
            ph, pw = person_bgra.shape[:2]
            if pw > 0 and ph > 0:
                scale = min(zone_largeur / pw, zone_hauteur / ph) * scale_z
                nw = max(1, int(pw * scale))
                nh = max(1, int(ph * scale))

                person_resized = cv2.resize(person_bgra, (nw, nh),
                                            interpolation=cv2.INTER_LANCZOS4)

                zone_cx = zone_x + zone_largeur // 2
                zone_cy = zone_y + zone_hauteur // 2
                px = zone_cx - nw // 2 + position_x
                py = zone_cy - nh // 2 + position_y

                alpha_p = person_resized[:, :, 3].astype(np.float32) / 255.0
                self._blend_onto(canvas, person_resized, alpha_p, px, py, nw, nh)

        # --- Premier plan ---
        if foreground_bgra is not None and foreground_bgra.size > 0:
            fh, fw = foreground_bgra.shape[:2]
            if (fh, fw) != (h_fond, w_fond):
                foreground_bgra = cv2.resize(foreground_bgra, (w_fond, h_fond),
                                             interpolation=cv2.INTER_LANCZOS4)
            if foreground_bgra.shape[2] == 4:
                alpha_f = foreground_bgra[:, :, 3].astype(np.float32) / 255.0
                a = alpha_f[:, :, np.newaxis]
                src = foreground_bgra[:, :, :3].astype(np.float32)
                dst = canvas[:, :, :3].astype(np.float32)
                canvas[:, :, :3] = np.clip(a * src + (1 - a) * dst, 0, 255).astype(np.uint8)
                canvas[:, :, 3] = np.maximum(canvas[:, :, 3], foreground_bgra[:, :, 3])

        return canvas  # BGRA natif OpenCV

    def composite_image(self, person_bgra, background_path, foreground_path,
                        position_x, position_y, scale_z, zone_info, set_config):
        """Composition finale pleine résolution (montage sauvegardé)."""
        if zone_info is None:
            raise ValueError("zone_info ne peut pas être None")

        background_bgr = cv2.imread(str(background_path))
        if background_bgr is None:
            raise FileNotFoundError(f"Impossible de charger {background_path}")

        foreground_bgra = self.load_foreground(foreground_path)

        return self._composite(
            person_bgra, background_bgr, foreground_bgra,
            position_x, position_y, scale_z,
            zone_info['largeur'], zone_info['hauteur'],
            zone_info['x'], zone_info['y']
        )

    def create_preview(self, frame, ui_background_bgr, ui_foreground_bgra,
                       position_x, position_y, scale_z, set_config):
        """
        Aperçu en direct avec les fichiers UI (600px) déjà en cache.
        position_x/y sont mis à l'échelle UI avant composition.
        scale_z est appliqué directement (indépendant de l'échelle UI).
        """
        try:
            if ui_background_bgr is None or ui_foreground_bgra is None:
                return None

            person_bgra, _ = self.extract_person(frame)
            if person_bgra is None:
                return None

            ui_pos_x = int(position_x * Config.UI_SCALE)
            ui_pos_y = int(position_y * Config.UI_SCALE)

            result_bgra = self._composite(
                person_bgra, ui_background_bgr, ui_foreground_bgra,
                ui_pos_x, ui_pos_y, scale_z,
                set_config.ui_zone_largeur, set_config.ui_zone_hauteur,
                set_config.ui_zone_x, set_config.ui_zone_y
            )

            # BGRA → RGB pour affichage Qt
            return cv2.cvtColor(result_bgra, cv2.COLOR_BGRA2RGB)

        except Exception as e:
            logger.error(f"Erreur create_preview: {e}")
            import traceback
            traceback.print_exc()
            return None

    def save_with_metadata(self, image, person_name, email, set_id):
        """Sauvegarde en JPEG avec métadonnées EXIF."""
        timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
        clean_name = "".join(c for c in person_name if c.isalnum() or c in " -_").strip()
        filename = f"salonBD_{clean_name}_{timestamp}_set{set_id}.jpg"
        filepath = Config.SAVE_DIR / filename

        # BGRA → RGB pour PIL/JPEG
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