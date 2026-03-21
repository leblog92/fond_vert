def change_set(self, index):
    """Changer le set actuel"""
    self.current_set = index + 1
    self.update_set_preview()
    set_config = Config.SETS[self.current_set]
    
    # Mettre à jour zone_info avec les valeurs du nouveau set
    self.zone_info = {
        'largeur': set_config.zone_largeur,
        'hauteur': set_config.zone_hauteur,
        'x': set_config.zone_x,
        'y': set_config.zone_y
    }
    
    # Mettre à jour l'affichage des dimensions
    self.update_set_info_display()
    
    logger.info(f"Set changé pour {self.current_set}, zone_info: {self.zone_info}")