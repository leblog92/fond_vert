# main.py
import sys
import os
import logging
from pathlib import Path
from datetime import datetime

from PyQt5.QtWidgets import (QApplication, QMainWindow, QWidget, QVBoxLayout, 
                             QHBoxLayout, QPushButton, QComboBox, QLabel, 
                             QGroupBox, QSlider, QSpinBox, QLineEdit, 
                             QFileDialog, QMessageBox, QGridLayout, QTabWidget,
                             QCheckBox)
from PyQt5.QtCore import Qt, QTimer, pyqtSignal
from PyQt5.QtGui import QImage, QPixmap, QFont, QPainter, QPen, QColor
import cv2
import numpy as np

from config import Config
from camera_manager import CameraThread, CameraScanner
from image_processor import GreenScreenProcessor

# Configuration du logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

class MainWindow(QMainWindow):
    def __init__(self):
        super().__init__()
        self.setWindowTitle("Studio Photo Fond Vert - Salon BD")
        self.setGeometry(100, 100, 1600, 900)
        
        # Initialisation
        self.current_set = 1
        self.camera_thread = None
        self.processor = GreenScreenProcessor()
        self.current_frame = None
        self.person_position_x = 0
        self.person_position_y = 0
        
        # Initialisation de zone_info avec les valeurs du set 1
        set_config = Config.SETS[1]
        self.zone_info = {
            'largeur': set_config.zone_largeur,
            'hauteur': set_config.zone_hauteur,
            'x': set_config.zone_x,
            'y': set_config.zone_y
        }
        
        self.preview_timer = QTimer()
        self.preview_timer.timeout.connect(self.update_montage_preview)
        
        # Configuration
        Config.ensure_save_dir()
        
        # Interface
        self.setup_ui()
        
        # Scanner initial des caméras
        self.scan_cameras()
        
    def update_set_info_display(self):
        """Affiche les informations du set en cours"""
        set_config = Config.SETS[self.current_set]
        info_text = (f"📐 Set {self.current_set}\n"
                     f"└─ Fond: {set_config.largeur_fond} x {set_config.hauteur_fond} px\n"
                     f"└─ Zone visible: {set_config.zone_largeur} x {set_config.zone_hauteur} px\n"
                     f"└─ Position zone: X={set_config.zone_x}, Y={set_config.zone_y}")
        
        # Mettre à jour le label si il existe
        if hasattr(self, 'set_info_label'):
            self.set_info_label.setText(info_text)
        
    def setup_ui(self):
        """Configuration de l'interface utilisateur"""
        central_widget = QWidget()
        self.setCentralWidget(central_widget)
        
        main_layout = QHBoxLayout(central_widget)
        
        # Panneau gauche - Caméra et paramètres
        left_panel = QWidget()
        left_layout = QVBoxLayout(left_panel)
        
        # Zone de la caméra
        camera_group = self.create_camera_group()
        left_layout.addWidget(camera_group)
        
        # Aperçu caméra (avec détourage)
        self.camera_label = QLabel("Aperçu caméra avec détourage")
        self.camera_label.setMinimumSize(640, 360)
        self.camera_label.setStyleSheet("border: 2px solid #444; background-color: #2b2b2b;")
        self.camera_label.setAlignment(Qt.AlignCenter)
        left_layout.addWidget(self.camera_label)
        
        # Paramètres de détourage
        chroma_group = self.create_chroma_group()
        left_layout.addWidget(chroma_group)
        
        # Panneau central - Aperçu du montage
        center_panel = QWidget()
        center_layout = QVBoxLayout(center_panel)
        
        # Aperçu du montage en direct
        preview_group = QGroupBox("Aperçu du montage en direct")
        preview_layout = QVBoxLayout()
        
        self.montage_label = QLabel("Aperçu du montage")
        self.montage_label.setMinimumSize(800, 450)
        self.montage_label.setStyleSheet("border: 2px solid #4CAF50; background-color: #2b2b2b;")
        self.montage_label.setAlignment(Qt.AlignCenter)
        preview_layout.addWidget(self.montage_label)
        
        # Checkbox pour activer/désactiver l'aperçu en direct
        self.preview_check = QCheckBox("Aperçu en direct du montage")
        self.preview_check.setChecked(True)
        self.preview_check.stateChanged.connect(self.toggle_live_preview)
        preview_layout.addWidget(self.preview_check)
        
        preview_group.setLayout(preview_layout)
        center_layout.addWidget(preview_group)
        
        # Panneau droit - Configuration et prise de vue
        right_panel = QWidget()
        right_layout = QVBoxLayout(right_panel)
        
        # Sélection du set
        set_group = self.create_set_group()
        right_layout.addWidget(set_group)
        
        # Ajustement position personne
        position_group = self.create_position_group()
        right_layout.addWidget(position_group)
        
        # Informations personne
        info_group = self.create_info_group()
        right_layout.addWidget(info_group)
        
        # Bouton de prise de vue
        self.create_capture_button()
        right_layout.addWidget(self.capture_button)
        
        # Ajout des panneaux au layout principal
        main_layout.addWidget(left_panel, 2)
        main_layout.addWidget(center_panel, 3)
        main_layout.addWidget(right_panel, 2)
        
    def create_camera_group(self):
        """Crée le groupe de contrôle de la caméra"""
        camera_group = QGroupBox("Caméra")
        camera_layout = QVBoxLayout()
        
        # Sélection caméra
        cam_select_layout = QHBoxLayout()
        self.camera_combo = QComboBox()
        self.camera_combo.setMinimumWidth(200)
        self.scan_button = QPushButton("Scanner les caméras")
        self.scan_button.clicked.connect(self.scan_cameras)
        cam_select_layout.addWidget(QLabel("Caméra:"))
        cam_select_layout.addWidget(self.camera_combo)
        cam_select_layout.addWidget(self.scan_button)
        camera_layout.addLayout(cam_select_layout)
        
        # Boutons contrôle caméra
        cam_control_layout = QHBoxLayout()
        self.start_button = QPushButton("Démarrer")
        self.start_button.clicked.connect(self.start_camera)
        self.stop_button = QPushButton("Arrêter")
        self.stop_button.clicked.connect(self.stop_camera)
        self.stop_button.setEnabled(False)
        cam_control_layout.addWidget(self.start_button)
        cam_control_layout.addWidget(self.stop_button)
        camera_layout.addLayout(cam_control_layout)
        
        camera_group.setLayout(camera_layout)
        return camera_group
    
    def create_chroma_group(self):
        """Crée le groupe des paramètres de détourage"""
        chroma_group = QGroupBox("Paramètres de détourage")
        chroma_layout = QGridLayout()
        
        # Plages de couleurs
        chroma_layout.addWidget(QLabel("Teinte min:"), 0, 0)
        self.hue_min = QSpinBox()
        self.hue_min.setRange(0, 180)
        self.hue_min.setValue(35)
        self.hue_min.valueChanged.connect(self.update_green_range)
        chroma_layout.addWidget(self.hue_min, 0, 1)
        
        chroma_layout.addWidget(QLabel("Teinte max:"), 0, 2)
        self.hue_max = QSpinBox()
        self.hue_max.setRange(0, 180)
        self.hue_max.setValue(85)
        self.hue_max.valueChanged.connect(self.update_green_range)
        chroma_layout.addWidget(self.hue_max, 0, 3)
        
        chroma_layout.addWidget(QLabel("Sat. min:"), 1, 0)
        self.sat_min = QSpinBox()
        self.sat_min.setRange(0, 255)
        self.sat_min.setValue(50)
        self.sat_min.valueChanged.connect(self.update_green_range)
        chroma_layout.addWidget(self.sat_min, 1, 1)
        
        chroma_layout.addWidget(QLabel("Lum. min:"), 1, 2)
        self.val_min = QSpinBox()
        self.val_min.setRange(0, 255)
        self.val_min.setValue(50)
        self.val_min.valueChanged.connect(self.update_green_range)
        chroma_layout.addWidget(self.val_min, 1, 3)
        
        # Paramètres morphologiques
        chroma_layout.addWidget(QLabel("Érosion:"), 2, 0)
        self.erode_slider = QSlider(Qt.Horizontal)
        self.erode_slider.setRange(0, 5)
        self.erode_slider.setValue(1)
        self.erode_slider.valueChanged.connect(self.update_morph_params)
        chroma_layout.addWidget(self.erode_slider, 2, 1)
        
        chroma_layout.addWidget(QLabel("Dilatation:"), 2, 2)
        self.dilate_slider = QSlider(Qt.Horizontal)
        self.dilate_slider.setRange(0, 5)
        self.dilate_slider.setValue(2)
        self.dilate_slider.valueChanged.connect(self.update_morph_params)
        chroma_layout.addWidget(self.dilate_slider, 2, 3)
        
        chroma_layout.addWidget(QLabel("Lissage:"), 3, 0)
        self.smooth_slider = QSlider(Qt.Horizontal)
        self.smooth_slider.setRange(1, 10)
        self.smooth_slider.setValue(5)
        self.smooth_slider.valueChanged.connect(self.update_morph_params)
        chroma_layout.addWidget(self.smooth_slider, 3, 1)
        
        chroma_group.setLayout(chroma_layout)
        return chroma_group
    
    def create_set_group(self):
        """Crée le groupe de sélection du set avec informations"""
        set_group = QGroupBox("Configuration du set")
        set_layout = QVBoxLayout()
        
        set_selector_layout = QHBoxLayout()
        set_selector_layout.addWidget(QLabel("Set:"))
        self.set_combo = QComboBox()
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
    
    def create_position_group(self):
        """Crée le groupe d'ajustement de position"""
        position_group = QGroupBox("Position de la personne")
        position_layout = QGridLayout()
        
        position_layout.addWidget(QLabel("X:"), 0, 0)
        self.pos_x_slider = QSlider(Qt.Horizontal)
        self.pos_x_slider.setRange(-200, 200)
        self.pos_x_slider.valueChanged.connect(self.update_person_position)
        position_layout.addWidget(self.pos_x_slider, 0, 1)
        self.pos_x_value = QLabel("0")
        position_layout.addWidget(self.pos_x_value, 0, 2)
        
        position_layout.addWidget(QLabel("Y:"), 1, 0)
        self.pos_y_slider = QSlider(Qt.Horizontal)
        self.pos_y_slider.setRange(-200, 200)
        self.pos_y_slider.valueChanged.connect(self.update_person_position)
        position_layout.addWidget(self.pos_y_slider, 1, 1)
        self.pos_y_value = QLabel("0")
        position_layout.addWidget(self.pos_y_value, 1, 2)
        
        position_group.setLayout(position_layout)
        return position_group
    
    def create_info_group(self):
        """Crée le groupe d'informations personne"""
        info_group = QGroupBox("Informations personne")
        info_layout = QVBoxLayout()
        
        info_layout.addWidget(QLabel("Nom de la personne:"))
        self.name_input = QLineEdit()
        self.name_input.setPlaceholderText("Ex: Jean Dupont")
        info_layout.addWidget(self.name_input)
        
        info_layout.addWidget(QLabel("Adresse email:"))
        self.email_input = QLineEdit()
        self.email_input.setPlaceholderText("exemple@email.com")
        info_layout.addWidget(self.email_input)
        
        info_group.setLayout(info_layout)
        return info_group
    
    def create_capture_button(self):
        """Crée le bouton de prise de vue"""
        self.capture_button = QPushButton("PRENDRE LA VUE")
        self.capture_button.setStyleSheet("""
            QPushButton {
                background-color: #4CAF50;
                color: white;
                font-size: 16px;
                font-weight: bold;
                padding: 15px;
                border-radius: 5px;
            }
            QPushButton:hover {
                background-color: #45a049;
            }
            QPushButton:disabled {
                background-color: #cccccc;
            }
        """)
        self.capture_button.clicked.connect(self.take_photo)
        self.capture_button.setEnabled(False)
        
    def scan_cameras(self):
        """Scanner les caméras disponibles"""
        self.camera_combo.clear()
        cameras = CameraScanner.scan_cameras()
        
        if cameras:
            for cam in cameras:
                self.camera_combo.addItem(cam['name'], cam['id'])
        else:
            self.camera_combo.addItem("Aucune caméra trouvée")
            
    def start_camera(self):
        """Démarrer la caméra"""
        if self.camera_combo.count() == 0 or "Aucune" in self.camera_combo.currentText():
            QMessageBox.warning(self, "Erreur", "Aucune caméra disponible")
            return
            
        camera_id = self.camera_combo.currentData()
        logger.info(f"Démarrage de la caméra {camera_id}")
        logger.info(f"zone_info actuel: {self.zone_info}")
        
        self.camera_thread = CameraThread()
        self.camera_thread.set_camera(camera_id)
        self.camera_thread.change_pixmap_signal.connect(self.update_image)
        self.camera_thread.camera_error.connect(self.handle_camera_error)
        self.camera_thread.start()
        
        self.start_button.setEnabled(False)
        self.stop_button.setEnabled(True)
        self.capture_button.setEnabled(True)
        
        # Démarrer l'aperçu du montage
        self.preview_timer.start(100)  # 10 fps
        
    def stop_camera(self):
        """Arrêter la caméra"""
        self.preview_timer.stop()
        
        if self.camera_thread:
            self.camera_thread.stop()
            self.camera_thread = None
            
        self.camera_label.clear()
        self.camera_label.setText("Aperçu caméra")
        self.montage_label.clear()
        self.montage_label.setText("Aperçu du montage")
        self.start_button.setEnabled(True)
        self.stop_button.setEnabled(False)
        self.capture_button.setEnabled(False)
        
    def update_image(self, frame):
        """Mettre à jour l'affichage de la caméra avec détourage"""
        self.current_frame = frame.copy()
        
        try:
            # Appliquer le détourage pour l'aperçu
            person_rgba, mask = self.processor.extract_person(frame)
            
            # Vérifier les dimensions et le type
            if person_rgba is not None and person_rgba.size > 0:
                # Afficher dans l'interface (version avec détourage)
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
            logger.error(f"Erreur update_image: {e}")
            pass
        
    def update_montage_preview(self):
        """Met à jour l'aperçu du montage en direct"""
        if not self.preview_check.isChecked() or self.current_frame is None:
            return
            
        # Vérifier que zone_info est initialisé
        if self.zone_info is None:
            logger.warning("zone_info n'est pas initialisé")
            return
            
        try:
            # Obtenir les chemins des fichiers
            assets_path = Path(__file__).parent / "assets"
            set_config = Config.SETS[self.current_set]
            fond_path = assets_path / set_config.fond_file
            pp_path = assets_path / set_config.pp_file
            
            if not fond_path.exists() or not pp_path.exists():
                logger.warning(f"Fichiers manquants: {fond_path} ou {pp_path}")
                return
                
            # Créer l'aperçu
            preview = self.processor.create_preview(
                self.current_frame, fond_path, pp_path,
                self.person_position_x, self.person_position_y,
                self.zone_info, set_config
            )
            
            if preview is not None and preview.size > 0:
                # Convertir pour l'affichage (RGB déjà)
                h, w, ch = preview.shape
                bytes_per_line = ch * w
                qt_image = QImage(preview.data, w, h, bytes_per_line, QImage.Format_RGB888)
                scaled_pixmap = QPixmap.fromImage(qt_image).scaled(
                    self.montage_label.size(), Qt.KeepAspectRatio, Qt.SmoothTransformation)
                self.montage_label.setPixmap(scaled_pixmap)
                    
        except Exception as e:
            logger.error(f"Erreur update_montage_preview: {e}")
            pass
            
    def toggle_live_preview(self, state):
        """Active/désactive l'aperçu en direct"""
        if state == Qt.Checked and self.camera_thread is not None:
            self.preview_timer.start(100)
        else:
            self.preview_timer.stop()
            self.montage_label.clear()
            self.montage_label.setText("Aperçu du montage")
        
    def handle_camera_error(self, error_msg):
        """Gérer les erreurs de caméra"""
        QMessageBox.critical(self, "Erreur caméra", error_msg)
        self.stop_camera()
        
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
        self.update_set_info_display()
        
    def update_set_preview(self):
        """Met à jour l'aperçu du set (fond + premier plan)"""
        set_config = Config.SETS[self.current_set]
        assets_path = Path(__file__).parent / "assets"
        
        fond_path = assets_path / set_config.fond_file
        pp_path = assets_path / set_config.pp_file
        
        if fond_path.exists() and pp_path.exists():
            try:
                # Charger les deux images
                fond = cv2.imread(str(fond_path))
                pp = cv2.imread(str(pp_path), cv2.IMREAD_UNCHANGED)
                
                # Redimensionner pour l'aperçu
                height = 200
                scale = height / fond.shape[0]
                width = int(fond.shape[1] * scale)
                
                fond_small = cv2.resize(fond, (width, height))
                
                # Créer une composition simple pour l'aperçu
                if pp.shape[2] == 4:
                    pp_small = cv2.resize(pp, (width, height))
                    # Composition rapide pour l'aperçu
                    alpha = pp_small[:, :, 3] / 255.0
                    for c in range(3):
                        fond_small[:, :, c] = (alpha * pp_small[:, :, c] + 
                                              (1 - alpha) * fond_small[:, :, c])
                
                # Convertir pour affichage
                rgb_image = cv2.cvtColor(fond_small, cv2.COLOR_BGR2RGB)
                h, w, ch = rgb_image.shape
                bytes_per_line = ch * w
                qt_image = QImage(rgb_image.data, w, h, bytes_per_line, QImage.Format_RGB888)
                self.set_preview.setPixmap(QPixmap.fromImage(qt_image))
            except Exception as e:
                logger.error(f"Erreur update_set_preview: {e}")
                self.set_preview.setText(f"Erreur chargement:\n{str(e)}")
        else:
            self.set_preview.setText(f"Fichiers non trouvés:\n{set_config.fond_file}\n{set_config.pp_file}")
            
    def update_green_range(self):
        """Met à jour la plage de détection du vert"""
        self.processor.update_green_range(
            self.hue_min.value(),
            self.hue_max.value(),
            self.sat_min.value(),
            self.val_min.value()
        )
        
    def update_morph_params(self):
        """Met à jour les paramètres morphologiques"""
        self.processor.update_morph_params(
            self.erode_slider.value(),
            self.dilate_slider.value(),
            self.smooth_slider.value()
        )
        
    def update_person_position(self):
        """Met à jour la position de la personne"""
        self.person_position_x = self.pos_x_slider.value()
        self.person_position_y = self.pos_y_slider.value()
        self.pos_x_value.setText(str(self.person_position_x))
        self.pos_y_value.setText(str(self.person_position_y))
        
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
            
            # Composer l'image finale
            final_image = self.processor.composite_image(
                person_rgba, fond_path, pp_path,
                self.person_position_x, self.person_position_y,
                self.zone_info, set_config
            )
            
            # Vérifier les dimensions
            h, w = final_image.shape[:2]
            
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
            logger.error(f"Erreur take_photo: {e}")
            QMessageBox.critical(self, "Erreur", f"Erreur lors de la sauvegarde:\n{str(e)}")
            
    def closeEvent(self, event):
        """Gérer la fermeture de l'application"""
        self.stop_camera()
        event.accept()

def main():
    app = QApplication(sys.argv)
    app.setStyle('Fusion')
    
    # Configuration de la police pour les caractères français
    font = QFont("Arial", 9)
    app.setFont(font)
    
    window = MainWindow()
    window.show()
    
    sys.exit(app.exec_())

if __name__ == "__main__":
    main()