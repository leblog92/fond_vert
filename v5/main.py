# main.py (extraits modifiés)
from PyQt5.QtWidgets import QProgressBar, QApplication  # Ajouter QProgressBar

class MainWindow(QMainWindow):
    def __init__(self):
        super().__init__()
        # ... (initialisation)
        
        # Ajouter une progress bar
        self.progress_bar = QProgressBar()
        self.progress_bar.setVisible(False)
        
    def setup_ui(self):
        # ... (dans le panneau droit, ajouter après le bouton de prise de vue)
        
        # Progress bar
        self.progress_bar.setMaximum(100)
        self.progress_bar.setVisible(False)
        right_layout.addWidget(self.progress_bar)
        
        # ... (reste du code)
    
    def start_camera(self):
        """Démarrer la caméra"""
        if self.camera_combo.count() == 0 or "Aucune" in self.camera_combo.currentText():
            QMessageBox.warning(self, "Erreur", "Aucune caméra disponible")
            return
            
        camera_id = self.camera_combo.currentData()
        
        # Utiliser la résolution réelle de la caméra
        self.camera_thread = CameraThread()
        self.camera_thread.set_camera(camera_id, use_preview=True)
        self.camera_thread.change_pixmap_signal.connect(self.update_image)
        self.camera_thread.camera_error.connect(self.handle_camera_error)
        self.camera_thread.start()
        
        self.start_button.setEnabled(False)
        self.stop_button.setEnabled(True)
        self.capture_button.setEnabled(True)
        
        # Démarrer l'aperçu avec un intervalle plus long pour moins de lag
        self.preview_timer.start(150)  # ~6-7 fps
        
    def update_image(self, frame):
        """Mettre à jour l'affichage de la caméra (redimensionné pour moins de lag)"""
        self.current_frame = frame.copy()
        
        try:
            # Redimensionner pour l'affichage (moins de CPU)
            small_frame = cv2.resize(frame, (Config.PREVIEW_WIDTH, Config.PREVIEW_HEIGHT),
                                     interpolation=cv2.INTER_LINEAR)
            
            # Appliquer le détourage sur la version réduite
            person_rgba, mask = self.processor.extract_person(small_frame)
            
            if person_rgba is not None and person_rgba.size > 0:
                if person_rgba.shape[2] == 4:
                    rgb_image = cv2.cvtColor(person_rgba, cv2.COLOR_BGRA2RGB)
                else:
                    rgb_image = cv2.cvtColor(person_rgba, cv2.COLOR_BGR2RGB)
                    
                h, w, ch = rgb_image.shape
                bytes_per_line = ch * w
                qt_image = QImage(rgb_image.data, w, h, bytes_per_line, QImage.Format_RGB888)
                scaled_pixmap = QPixmap.fromImage(qt_image).scaled(
                    self.camera_label.size(), Qt.KeepAspectRatio, Qt.SmoothTransformation)
                self.camera_label.setPixmap(scaled_pixmap)
        except Exception as e:
            pass
    
    def take_photo(self):
        """Prendre une photo avec progress bar"""
        if self.current_frame is None:
            QMessageBox.warning(self, "Erreur", "Aucune image disponible")
            return
            
        person_name = self.name_input.text().strip()
        email = self.email_input.text().strip()
        
        if not person_name:
            QMessageBox.warning(self, "Erreur", "Veuillez entrer un nom")
            return
            
        if not email:
            QMessageBox.warning(self, "Erreur", "Veuillez entrer une adresse email")
            return
        
        # Désactiver le bouton pendant le traitement
        self.capture_button.setEnabled(False)
        self.progress_bar.setVisible(True)
        self.progress_bar.setValue(0)
        
        try:
            # Étape 1: Extraction
            self.progress_bar.setValue(20)
            QApplication.processEvents()
            
            assets_path = Path(__file__).parent / "assets"
            set_config = Config.SETS[self.current_set]
            fond_path = assets_path / set_config.fond_file if set_config.fond_file else None
            pp_path = assets_path / set_config.pp_file if set_config.pp_file else None
            
            # Étape 2: Extraction personne
            self.progress_bar.setValue(40)
            QApplication.processEvents()
            person_rgba, _ = self.processor.extract_person(self.current_frame)
            
            # Étape 3: Composition
            self.progress_bar.setValue(60)
            QApplication.processEvents()
            
            final_image = self.processor.composite_image(
                person_rgba, fond_path, pp_path,
                self.person_position_x, self.person_position_y,
                self.zone_info, set_config
            )
            
            # Étape 4: Sauvegarde
            self.progress_bar.setValue(80)
            QApplication.processEvents()
            
            filepath = self.processor.save_with_metadata(
                final_image, person_name, email, self.current_set
            )
            
            self.progress_bar.setValue(100)
            QApplication.processEvents()
            
            # Message de succès (sans proposition d'ouvrir le dossier)
            h, w = final_image.shape[:2]
            QMessageBox.information(self, "Succès", 
                                   f"Photo sauvegardée avec succès!\n\n"
                                   f"📁 {filepath.name}\n"
                                   f"📐 Dimensions: {w} x {h} pixels\n"
                                   f"👤 Personne: {person_name}\n"
                                   f"📧 Email: {email}")
                
        except Exception as e:
            QMessageBox.critical(self, "Erreur", f"Erreur lors de la sauvegarde:\n{str(e)}")
            
        finally:
            self.progress_bar.setVisible(False)
            self.capture_button.setEnabled(True)
    
    def create_set_group(self):
        """Crée le groupe de sélection du set avec Set 0"""
        set_group = QGroupBox("Configuration du set")
        set_layout = QVBoxLayout()
        
        set_selector_layout = QHBoxLayout()
        set_selector_layout.addWidget(QLabel("Set:"))
        self.set_combo = QComboBox()
        
        # Ajouter Set 0 (fond vert uniquement)
        self.set_combo.addItem("Set 0 - Fond vert uniquement")
        for i in range(1, 5):
            self.set_combo.addItem(f"Set {i}")
            
        self.set_combo.currentIndexChanged.connect(self.change_set)
        set_selector_layout.addWidget(self.set_combo)
        set_layout.addLayout(set_selector_layout)
        
        # Informations sur le set
        self.set_info_label = QLabel("")
        self.set_info_label.setStyleSheet("background-color: #f0f0f0; padding: 5px; border-radius: 3px; font-family: monospace;")
        self.set_info_label.setWordWrap(True)
        set_layout.addWidget(self.set_info_label)
        
        # Aperçu du set
        self.set_preview = QLabel("Aperçu du set")
        self.set_preview.setMinimumSize(300, 200)
        self.set_preview.setStyleSheet("border: 1px solid black; background-color: #2b2b2b;")
        self.set_preview.setAlignment(Qt.AlignCenter)
        set_layout.addWidget(self.set_preview)
        
        set_group.setLayout(set_layout)
        return set_group
    
    def change_set(self, index):
        """Changer le set actuel (index 0 = Set 0)"""
        self.current_set = index  # Index 0 = Set 0
        self.update_set_preview()
        set_config = Config.SETS[self.current_set]
        
        self.zone_info = {
            'largeur': set_config.zone_largeur,
            'hauteur': set_config.zone_hauteur,
            'x': set_config.zone_x,
            'y': set_config.zone_y
        }
        
        self.update_set_info_display()
        logger.info(f"Set changé pour {self.current_set}")