def take_photo(self):
    """Prendre une photo et l'enregistrer"""
    if self.current_frame is None:
        QMessageBox.warning(self, "Erreur", "Aucune image disponible")
        return
        
    # Vérifier les informations
    person_name = self.name_input.text().strip()
    email = self.email_input.text().strip()
    
    if not person_name:
        QMessageBox.warning(self, "Erreur", "Veuillez entrer un nom")
        return
        
    if not email:
        QMessageBox.warning(self, "Erreur", "Veuillez entrer une adresse email")
        return
        
    try:
        # Obtenir les chemins des fichiers
        assets_path = Path(__file__).parent / "assets"
        set_config = Config.SETS[self.current_set]
        fond_path = assets_path / set_config.fond_file
        pp_path = assets_path / set_config.pp_file
        
        if not fond_path.exists():
            QMessageBox.critical(self, "Erreur", 
                               f"Fichier de fond non trouvé: {fond_path}")
            return
            
        if not pp_path.exists():
            QMessageBox.critical(self, "Erreur", 
                               f"Fichier de premier plan non trouvé: {pp_path}")
            return
        
        # Extraire la personne
        person_rgba, _ = self.processor.extract_person(self.current_frame)
        
        # Composer l'image finale (gardera les dimensions exactes du fond)
        final_image = self.processor.composite_image(
            person_rgba, fond_path, pp_path,
            self.person_position_x, self.person_position_y,
            self.zone_info, set_config
        )
        
        # Vérifier les dimensions
        h, w = final_image.shape[:2]
        logger.info(f"Image finale créée: {w}x{h} px")
        
        # Sauvegarde
        filepath = self.processor.save_with_metadata(
            final_image, person_name, email, self.current_set
        )
        
        # Afficher un message avec les dimensions
        QMessageBox.information(self, "Succès", 
                               f"Photo sauvegardée:\n{filepath}\n"
                               f"Dimensions: {w} x {h} pixels")
        
        # Option : ouvrir le dossier
        reply = QMessageBox.question(self, "Ouvrir le dossier", 
                                    "Voulez-vous ouvrir le dossier de sauvegarde?",
                                    QMessageBox.Yes | QMessageBox.No)
        if reply == QMessageBox.Yes:
            os.startfile(Config.SAVE_DIR)
            
    except Exception as e:
        QMessageBox.critical(self, "Erreur", f"Erreur lors de la sauvegarde:\n{str(e)}")