def change_set(self, index):
    """Changer le set actuel"""
    self.current_set = index + 1
    self.update_set_preview()
    set_config = Config.SETS[self.current_set]
    self.zone_info = {
        'largeur': set_config.zone_largeur,
        'hauteur': set_config.zone_hauteur,
        'x': set_config.zone_x,
        'y': set_config.zone_y
    }
    
    # Mettre à jour l'affichage des dimensions
    info_text = (f"📐 Dimensions du set {self.current_set}:\n"
                 f"└─ Fond: {set_config.largeur_fond} x {set_config.hauteur_fond} px\n"
                 f"└─ Zone caméra: {set_config.zone_largeur} x {set_config.zone_hauteur} px\n"
                 f"└─ Position zone: X={set_config.zone_x}, Y={set_config.zone_y}")
    self.set_info_label.setText(info_text)