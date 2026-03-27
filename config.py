# config.py
import os
from dataclasses import dataclass
from pathlib import Path

@dataclass
class SetConfig:
    """Configuration pour chaque set"""
    # Fichiers pleine résolution — montage final (2000px de large)
    fond_file: str
    pp_file: str
    largeur_fond: int
    hauteur_fond: int
    zone_largeur: int
    zone_hauteur: int
    zone_x: int
    zone_y: int

    # Fichiers UI — prévisualisation (600px de large, scale=0.3)
    ui_fond_file: str
    ui_pp_file: str
    ui_largeur_fond: int
    ui_hauteur_fond: int
    ui_zone_largeur: int
    ui_zone_hauteur: int
    ui_zone_x: int
    ui_zone_y: int


class Config:
    # Facteur d'échelle entre les fichiers UI et les fichiers originaux
    UI_SCALE = 0.3  # 600 / 2000

    SETS = {
        1: SetConfig(
            fond_file="fond1.jpg",  pp_file="pp1.png",
            largeur_fond=2000,      hauteur_fond=1688,
            zone_largeur=1061,      zone_hauteur=597,
            zone_x=-80,             zone_y=959,
            ui_fond_file="UI_fond1.jpg",  ui_pp_file="UI_pp1.png",
            ui_largeur_fond=600,          ui_hauteur_fond=506,
            ui_zone_largeur=318,          ui_zone_hauteur=179,
            ui_zone_x=-24,                ui_zone_y=287,
        ),
        2: SetConfig(
            fond_file="fond2.jpg",  pp_file="pp2.png",
            largeur_fond=2000,      hauteur_fond=1414,
            zone_largeur=2286,      zone_hauteur=1286,
            zone_x=-137,            zone_y=68,
            ui_fond_file="UI_fond2.jpg",  ui_pp_file="UI_pp2.png",
            ui_largeur_fond=600,          ui_hauteur_fond=424,
            ui_zone_largeur=685,          ui_zone_hauteur=385,
            ui_zone_x=-41,                ui_zone_y=20,
        ),
        3: SetConfig(
            fond_file="fond3.jpg",  pp_file="pp3.png",
            largeur_fond=2000,      hauteur_fond=2632,
            zone_largeur=1267,      zone_hauteur=711,
            zone_x=942,             zone_y=1713,
            ui_fond_file="UI_fond3.jpg",  ui_pp_file="UI_pp3.png",
            ui_largeur_fond=600,          ui_hauteur_fond=789,
            ui_zone_largeur=380,          ui_zone_hauteur=213,
            ui_zone_x=282,                ui_zone_y=513,
        ),
        4: SetConfig(
            fond_file="fond4.jpg",  pp_file="pp4.png",
            largeur_fond=2000,      hauteur_fond=2633,
            zone_largeur=1890,      zone_hauteur=1063,
            zone_x=74,              zone_y=1253,
            ui_fond_file="UI_fond4.jpg",  ui_pp_file="UI_pp4.png",
            ui_largeur_fond=600,          ui_hauteur_fond=789,
            ui_zone_largeur=567,          ui_zone_hauteur=318,
            ui_zone_x=22,                 ui_zone_y=375,
        ),
    }

    SAVE_DIR = Path(os.environ['USERPROFILE']) / "Pictures" / "salonBD"

    DEFAULT_GREEN_RANGE = {
        'lower_hue': 35,
        'upper_hue': 85,
        'lower_saturation': 50,
        'lower_value': 50
    }

    CAMERA_WIDTH  = 1280
    CAMERA_HEIGHT = 720

    @staticmethod
    def ensure_save_dir():
        Config.SAVE_DIR.mkdir(parents=True, exist_ok=True)
        return Config.SAVE_DIR
