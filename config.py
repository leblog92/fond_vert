# config.py
import os
from dataclasses import dataclass
from pathlib import Path

@dataclass
class SetConfig:
    """Configuration pour chaque set"""
    fond_file: str
    pp_file: str
    largeur_fond: int
    hauteur_fond: int
    zone_largeur: int
    zone_hauteur: int
    zone_x: int
    zone_y: int

class Config:
    # Configuration des sets
    SETS = {
        1: SetConfig("fond1.png", "pp1.png", 2000, 1688, 1061, 597, -80, 959),
        2: SetConfig("fond2.png", "pp2.png", 2000, 1414, 2286, 1286, -137, 68),
        3: SetConfig("fond3.png", "pp3.png", 2000, 2632, 1267, 711, 942, 1713),
        4: SetConfig("fond4.png", "pp4.png", 2000, 2633, 1890, 1063, 74, 1253)
    }
    
    # Dossier de sauvegarde
    SAVE_DIR = Path(os.environ['USERPROFILE']) / "Pictures" / "salonBD"
    
    # Paramètres par défaut pour le détourage
    DEFAULT_GREEN_RANGE = {
        'lower_hue': 35,
        'upper_hue': 85,
        'lower_saturation': 50,
        'lower_value': 50
    }
    
    # Résolution caméra
    CAMERA_WIDTH = 1280
    CAMERA_HEIGHT = 720
    
    @staticmethod
    def ensure_save_dir():
        """Crée le dossier de sauvegarde s'il n'existe pas"""
        Config.SAVE_DIR.mkdir(parents=True, exist_ok=True)
        return Config.SAVE_DIR