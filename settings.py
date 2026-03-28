# settings.py
import json
import logging
from pathlib import Path

logger = logging.getLogger(__name__)

SETTINGS_FILE = Path(__file__).parent / "settings.json"

DEFAULTS = {
    # Détourage
    "hue_min":    35,
    "hue_max":    85,
    "sat_min":    50,
    "val_min":    50,
    "erode":       1,
    "dilate":      2,
    "smooth":      5,
    # Position / zoom
    "pos_x":       0,
    "pos_y":       0,
    "pos_z":     100,   # en %, 100 = taille normale
    # Set actif
    "current_set": 1,
    # UI
    "show_mask":  False,
    "live_preview": True,
}


def load() -> dict:
    """Charge settings.json et complète les clés manquantes avec les défauts."""
    if not SETTINGS_FILE.exists():
        return dict(DEFAULTS)
    try:
        with open(SETTINGS_FILE, "r", encoding="utf-8") as f:
            data = json.load(f)
        # Fusionner avec les défauts pour les clés absentes
        merged = dict(DEFAULTS)
        merged.update(data)
        return merged
    except Exception as e:
        logger.warning(f"Impossible de lire settings.json ({e}), utilisation des défauts")
        return dict(DEFAULTS)


def save(settings: dict) -> None:
    """Sauvegarde le dictionnaire dans settings.json."""
    try:
        with open(SETTINGS_FILE, "w", encoding="utf-8") as f:
            json.dump(settings, f, indent=2, ensure_ascii=False)
        logger.info(f"Paramètres sauvegardés dans {SETTINGS_FILE}")
    except Exception as e:
        logger.error(f"Impossible de sauvegarder settings.json : {e}")