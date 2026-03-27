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
                             QCheckBox, QProgressBar, QDoubleSpinBox)
from PyQt5.QtCore import Qt, QTimer, pyqtSignal
from PyQt5.QtGui import QImage, QPixmap, QFont
import cv2
import numpy as np

from config import Config
from camera_manager import CameraThread, CameraScanner
from image_processor import GreenScreenProcessor

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)


class MainWindow(QMainWindow):
    def __init__(self):
        super().__init__()
        self.setWindowTitle("Studio Photo Fond Vert - Salon BD")
        self.setGeometry(100, 100, 1600, 900)

        self.current_set = 1
        self.camera_thread = None
        self.processor = GreenScreenProcessor()
        self.current_frame = None
        self.person_position_x = 0
        self.person_position_y = 0
        self.person_scale_z = 1.0   # correcteur zoom (1.0 = taille normale)
        self._camera_ready = False  # True dès la première frame reçue

        # Cache UI : clé = set_id, valeur = (background_bgr, foreground_bgra)
        self._ui_cache = {}

        # Coordonnées pleine résolution pour le montage final
        set_config = Config.SETS[1]
        self.zone_info = {
            'largeur': set_config.zone_largeur,
            'hauteur': set_config.zone_hauteur,
            'x': set_config.zone_x,
            'y': set_config.zone_y
        }

        # Timer aperçu montage (5 fps)
        self.preview_timer = QTimer()
        self.preview_timer.timeout.connect(self.update_montage_preview)

        # Timer barre de progression caméra
        # 25s d'attente max → 250 ticks à 100ms → +0.36% par tick pour atteindre 90%
        self._progress_timer = QTimer()
        self._progress_timer.setInterval(100)
        self._progress_timer.timeout.connect(self._tick_progress)
        self._progress_value = 0.0

        Config.ensure_save_dir()
        self.setup_ui()
        self.scan_cameras()

    # ------------------------------------------------------------------
    # Cache UI
    # ------------------------------------------------------------------

    def _get_ui_assets(self, set_id):
        """Retourne (background_bgr, foreground_bgra) depuis le cache UI."""
        if set_id not in self._ui_cache:
            assets_path = Path(__file__).parent / "assets"
            cfg = Config.SETS[set_id]
            fond_path = assets_path / cfg.ui_fond_file
            pp_path   = assets_path / cfg.ui_pp_file

            if not fond_path.exists() or not pp_path.exists():
                logger.warning(f"Fichiers UI manquants set {set_id}: {fond_path}, {pp_path}")
                return None, None

            bg = cv2.imread(str(fond_path))
            pp = cv2.imread(str(pp_path), cv2.IMREAD_UNCHANGED)

            if bg is None or pp is None:
                logger.error(f"Lecture impossible fichiers UI set {set_id}")
                return None, None

            if pp.shape[2] == 3:
                pp_bgra = cv2.cvtColor(pp, cv2.COLOR_BGR2BGRA)
            else:
                pp_bgra = pp.copy()

            self._ui_cache[set_id] = (bg, pp_bgra)
            logger.info(f"Cache UI set {set_id} : fond={bg.shape}, pp={pp_bgra.shape}")

        return self._ui_cache[set_id]

    # ------------------------------------------------------------------
    # Interface utilisateur
    # ------------------------------------------------------------------

    def update_set_info_display(self):
        set_config = Config.SETS[self.current_set]
        info_text = (f"📐 Set {self.current_set}\n"
                     f"└─ Fond: {set_config.largeur_fond} x {set_config.hauteur_fond} px\n"
                     f"└─ Zone visible: {set_config.zone_largeur} x {set_config.zone_hauteur} px\n"
                     f"└─ Position zone: X={set_config.zone_x}, Y={set_config.zone_y}")
        if hasattr(self, 'set_info_label'):
            self.set_info_label.setText(info_text)

    def setup_ui(self):
        central_widget = QWidget()
        self.setCentralWidget(central_widget)
        main_layout = QHBoxLayout(central_widget)

        # Panneau gauche
        left_panel = QWidget()
        left_layout = QVBoxLayout(left_panel)
        left_layout.addWidget(self.create_camera_group())

        self.camera_label = QLabel("Aperçu caméra avec détourage")
        self.camera_label.setMinimumSize(640, 360)
        self.camera_label.setStyleSheet("border: 2px solid #444; background-color: #2b2b2b;")
        self.camera_label.setAlignment(Qt.AlignCenter)
        left_layout.addWidget(self.camera_label)
        left_layout.addWidget(self.create_chroma_group())

        # Panneau central
        center_panel = QWidget()
        center_layout = QVBoxLayout(center_panel)
        preview_group = QGroupBox("Aperçu du montage en direct")
        preview_layout = QVBoxLayout()

        self.montage_label = QLabel("Aperçu du montage")
        self.montage_label.setMinimumSize(800, 450)
        self.montage_label.setStyleSheet("border: 2px solid #4CAF50; background-color: #2b2b2b;")
        self.montage_label.setAlignment(Qt.AlignCenter)
        preview_layout.addWidget(self.montage_label)

        self.preview_check = QCheckBox("Aperçu en direct du montage")
        self.preview_check.setChecked(True)
        self.preview_check.stateChanged.connect(self.toggle_live_preview)
        preview_layout.addWidget(self.preview_check)
        preview_group.setLayout(preview_layout)
        center_layout.addWidget(preview_group)

        # Panneau droit
        right_panel = QWidget()
        right_layout = QVBoxLayout(right_panel)
        right_layout.addWidget(self.create_set_group())
        right_layout.addWidget(self.create_position_group())
        right_layout.addWidget(self.create_info_group())
        self.create_capture_button()
        right_layout.addWidget(self.capture_button)

        # Bouton ouvrir le dossier (permanent, pas de question après chaque prise)
        self.open_folder_button = QPushButton("📂 Ouvrir le dossier de sauvegarde")
        self.open_folder_button.clicked.connect(lambda: os.startfile(Config.SAVE_DIR))
        self.open_folder_button.setStyleSheet("""
            QPushButton {
                background-color: #2196F3;
                color: white;
                font-size: 12px;
                padding: 8px;
                border-radius: 4px;
            }
            QPushButton:hover { background-color: #1976D2; }
        """)
        right_layout.addWidget(self.open_folder_button)

        main_layout.addWidget(left_panel, 2)
        main_layout.addWidget(center_panel, 3)
        main_layout.addWidget(right_panel, 2)

    def create_camera_group(self):
        camera_group = QGroupBox("Caméra")
        camera_layout = QVBoxLayout()

        cam_select_layout = QHBoxLayout()
        self.camera_combo = QComboBox()
        self.camera_combo.setMinimumWidth(200)
        self.scan_button = QPushButton("Scanner les caméras")
        self.scan_button.clicked.connect(self.scan_cameras)
        cam_select_layout.addWidget(QLabel("Caméra:"))
        cam_select_layout.addWidget(self.camera_combo)
        cam_select_layout.addWidget(self.scan_button)
        camera_layout.addLayout(cam_select_layout)

        cam_control_layout = QHBoxLayout()
        self.start_button = QPushButton("Démarrer")
        self.start_button.clicked.connect(self.start_camera)
        self.stop_button = QPushButton("Arrêter")
        self.stop_button.clicked.connect(self.stop_camera)
        self.stop_button.setEnabled(False)
        cam_control_layout.addWidget(self.start_button)
        cam_control_layout.addWidget(self.stop_button)
        camera_layout.addLayout(cam_control_layout)

        # Barre de progression : calibrée pour ~25s d'attente
        self.camera_progress = QProgressBar()
        self.camera_progress.setRange(0, 1000)   # précision 0.1%
        self.camera_progress.setValue(0)
        self.camera_progress.setTextVisible(True)
        self.camera_progress.setFormat("Initialisation de la caméra...")
        self.camera_progress.setVisible(False)
        camera_layout.addWidget(self.camera_progress)

        camera_group.setLayout(camera_layout)
        return camera_group

    def create_chroma_group(self):
        chroma_group = QGroupBox("Paramètres de détourage")
        chroma_layout = QGridLayout()

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

        self.set_info_label = QLabel("")
        self.set_info_label.setStyleSheet(
            "background-color: #f0f0f0; padding: 5px; border-radius: 3px; font-family: monospace;")
        self.set_info_label.setWordWrap(True)
        set_layout.addWidget(self.set_info_label)

        self.set_preview = QLabel("Aperçu du set")
        self.set_preview.setMinimumSize(300, 200)
        self.set_preview.setStyleSheet("border: 1px solid black; background-color: #2b2b2b;")
        self.set_preview.setAlignment(Qt.AlignCenter)
        set_layout.addWidget(self.set_preview)

        set_group.setLayout(set_layout)
        return set_group

    def create_position_group(self):
        position_group = QGroupBox("Position / Zoom de la personne")
        position_layout = QGridLayout()

        # X
        position_layout.addWidget(QLabel("X:"), 0, 0)
        self.pos_x_slider = QSlider(Qt.Horizontal)
        self.pos_x_slider.setRange(-500, 500)
        self.pos_x_slider.valueChanged.connect(self.update_person_position)
        position_layout.addWidget(self.pos_x_slider, 0, 1)
        self.pos_x_value = QLabel("0")
        position_layout.addWidget(self.pos_x_value, 0, 2)

        # Y
        position_layout.addWidget(QLabel("Y:"), 1, 0)
        self.pos_y_slider = QSlider(Qt.Horizontal)
        self.pos_y_slider.setRange(-500, 500)
        self.pos_y_slider.valueChanged.connect(self.update_person_position)
        position_layout.addWidget(self.pos_y_slider, 1, 1)
        self.pos_y_value = QLabel("0")
        position_layout.addWidget(self.pos_y_value, 1, 2)

        # Z (zoom) — slider de 50% à 200%, pas de 1%
        position_layout.addWidget(QLabel("Z (zoom):"), 2, 0)
        self.pos_z_slider = QSlider(Qt.Horizontal)
        self.pos_z_slider.setRange(50, 200)   # 50% .. 200%
        self.pos_z_slider.setValue(100)        # 100% = taille normale
        self.pos_z_slider.valueChanged.connect(self.update_person_position)
        position_layout.addWidget(self.pos_z_slider, 2, 1)
        self.pos_z_value = QLabel("100%")
        position_layout.addWidget(self.pos_z_value, 2, 2)

        # Bouton reset
        reset_btn = QPushButton("Réinitialiser")
        reset_btn.clicked.connect(self.reset_position)
        position_layout.addWidget(reset_btn, 3, 0, 1, 3)

        position_group.setLayout(position_layout)
        return position_group

    def create_info_group(self):
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
            QPushButton:hover { background-color: #45a049; }
            QPushButton:disabled { background-color: #cccccc; }
        """)
        self.capture_button.clicked.connect(self.take_photo)
        self.capture_button.setEnabled(False)

    # ------------------------------------------------------------------
    # Caméra
    # ------------------------------------------------------------------

    def scan_cameras(self):
        """Scanner les caméras — sans résolution entre parenthèses"""
        self.camera_combo.clear()
        cameras = CameraScanner.scan_cameras()
        if cameras:
            for i, cam in enumerate(cameras):
                self.camera_combo.addItem(f"Caméra {i}", cam['id'])
        else:
            self.camera_combo.addItem("Aucune caméra trouvée")

    def start_camera(self):
        if self.camera_combo.count() == 0 or "Aucune" in self.camera_combo.currentText():
            QMessageBox.warning(self, "Erreur", "Aucune caméra disponible")
            return

        camera_id = self.camera_combo.currentData()
        self._camera_ready = False
        self._progress_value = 0.0

        # Barre de progression calibrée pour ~25s
        # Plage 0..1000, tick 100ms, +3.6 par tick → 90% (900/1000) en ~25s
        self.camera_progress.setValue(0)
        self.camera_progress.setFormat("Initialisation de la caméra...")
        self.camera_progress.setVisible(True)
        self._progress_timer.start()

        self.camera_thread = CameraThread()
        self.camera_thread.set_camera(camera_id)
        self.camera_thread.change_pixmap_signal.connect(self.update_image)
        self.camera_thread.camera_error.connect(self.handle_camera_error)
        self.camera_thread.start()

        self.start_button.setEnabled(False)
        self.stop_button.setEnabled(True)
        self.capture_button.setEnabled(True)
        self.preview_timer.start(200)

    def _tick_progress(self):
        """Avance la barre jusqu'à 90% (900/1000) puis attend la première frame."""
        if self._camera_ready:
            # Caméra prête : compléter à 100% et masquer
            self.camera_progress.setValue(1000)
            self.camera_progress.setFormat("Caméra prête ✓")
            self._progress_timer.stop()
            QTimer.singleShot(800, lambda: self.camera_progress.setVisible(False))
        else:
            if self._progress_value < 900:
                self._progress_value += 3.6   # 900 / 250 ticks (25s × 10 ticks/s)
                self.camera_progress.setValue(int(self._progress_value))

    def _safe_stop_thread(self):
        """Arrête le thread caméra sans bloquer l'UI indéfiniment."""
        if self.camera_thread is None:
            return
        self.camera_thread.stop()
        # Attendre max 3s que le thread se termine proprement
        if not self.camera_thread.wait(3000):
            logger.warning("Le thread caméra n'a pas répondu dans les 3s, terminaison forcée")
            self.camera_thread.terminate()
            self.camera_thread.wait(1000)
        self.camera_thread = None

    def stop_camera(self):
        """Arrêt propre et sécurisé de la caméra."""
        # 1. Stopper tous les timers d'abord pour éviter les appels pendant l'arrêt
        self._progress_timer.stop()
        self.preview_timer.stop()
        self.camera_progress.setVisible(False)

        # 2. Arrêter le thread proprement
        self._safe_stop_thread()

        # 3. Réinitialiser l'état
        self._camera_ready = False
        self.current_frame = None
        self.camera_label.clear()
        self.camera_label.setText("Aperçu caméra")
        self.montage_label.clear()
        self.montage_label.setText("Aperçu du montage")
        self.set_preview.clear()
        self.set_preview.setText("Aperçu du set")
        self.start_button.setEnabled(True)
        self.stop_button.setEnabled(False)
        self.capture_button.setEnabled(False)

    def update_image(self, frame):
        """Affichage caméra gauche avec détourage."""
        self.current_frame = frame.copy()

        # Première frame reçue : marquer prête ET afficher l'aperçu du set
        if not self._camera_ready:
            self._camera_ready = True
            self.update_set_preview()
            self.update_set_info_display()

        try:
            person_bgra, _ = self.processor.extract_person(frame)
            if person_bgra is not None and person_bgra.size > 0:
                rgb_image = cv2.cvtColor(person_bgra, cv2.COLOR_BGRA2RGB)
                h, w, ch = rgb_image.shape
                qt_image = QImage(rgb_image.data, w, h, ch * w, QImage.Format_RGB888)
                scaled_pixmap = QPixmap.fromImage(qt_image).scaled(
                    self.camera_label.size(), Qt.KeepAspectRatio, Qt.SmoothTransformation)
                self.camera_label.setPixmap(scaled_pixmap)
        except Exception as e:
            logger.error(f"Erreur update_image: {e}")

    def update_montage_preview(self):
        """Aperçu montage central — fichiers UI (600px) en cache"""
        if not self.preview_check.isChecked() or self.current_frame is None:
            return

        try:
            set_config = Config.SETS[self.current_set]
            ui_bg, ui_pp = self._get_ui_assets(self.current_set)
            if ui_bg is None:
                return

            preview = self.processor.create_preview(
                self.current_frame, ui_bg, ui_pp,
                self.person_position_x, self.person_position_y,
                self.person_scale_z,
                set_config
            )

            if preview is not None and preview.size > 0:
                h, w, ch = preview.shape
                qt_image = QImage(preview.data, w, h, ch * w, QImage.Format_RGB888)
                scaled_pixmap = QPixmap.fromImage(qt_image).scaled(
                    self.montage_label.size(), Qt.KeepAspectRatio, Qt.SmoothTransformation)
                self.montage_label.setPixmap(scaled_pixmap)

        except Exception as e:
            logger.error(f"Erreur update_montage_preview: {e}")

    def toggle_live_preview(self, state):
        if state == Qt.Checked and self.camera_thread is not None:
            self.preview_timer.start(200)
        else:
            self.preview_timer.stop()
            self.montage_label.clear()
            self.montage_label.setText("Aperçu du montage")

    def handle_camera_error(self, error_msg):
        self._progress_timer.stop()
        self.camera_progress.setVisible(False)
        QMessageBox.critical(self, "Erreur caméra", error_msg)
        self.stop_camera()

    # ------------------------------------------------------------------
    # Set
    # ------------------------------------------------------------------

    def change_set(self, index):
        self.current_set = index + 1
        # N'afficher l'aperçu que si la caméra est déjà active
        if self._camera_ready:
            self.update_set_preview()
        set_config = Config.SETS[self.current_set]
        self.zone_info = {
            'largeur': set_config.zone_largeur,
            'hauteur': set_config.zone_hauteur,
            'x': set_config.zone_x,
            'y': set_config.zone_y
        }
        self.update_set_info_display()
        logger.info(f"Set {self.current_set}, zone_info: {self.zone_info}")

    def update_set_preview(self):
        """Aperçu statique fond+pp dans le panneau droit via cache UI"""
        try:
            ui_bg, ui_pp = self._get_ui_assets(self.current_set)
            if ui_bg is None:
                self.set_preview.setText("Fichiers UI non trouvés")
                return

            fond_small = ui_bg.copy()
            if ui_pp is not None and ui_pp.shape[2] == 4:
                if ui_pp.shape[:2] != ui_bg.shape[:2]:
                    ui_pp_r = cv2.resize(ui_pp, (ui_bg.shape[1], ui_bg.shape[0]))
                else:
                    ui_pp_r = ui_pp
                alpha = ui_pp_r[:, :, 3].astype(np.float32) / 255.0
                a = alpha[:, :, np.newaxis]
                src = ui_pp_r[:, :, :3].astype(np.float32)
                dst = fond_small.astype(np.float32)
                fond_small = np.clip(a * src + (1 - a) * dst, 0, 255).astype(np.uint8)

            rgb_image = cv2.cvtColor(fond_small, cv2.COLOR_BGR2RGB)
            h, w, ch = rgb_image.shape
            qt_image = QImage(rgb_image.data, w, h, ch * w, QImage.Format_RGB888)
            self.set_preview.setPixmap(QPixmap.fromImage(qt_image).scaled(
                self.set_preview.size(), Qt.KeepAspectRatio, Qt.SmoothTransformation))

        except Exception as e:
            logger.error(f"Erreur update_set_preview: {e}")
            self.set_preview.setText(f"Erreur: {str(e)}")

    # ------------------------------------------------------------------
    # Paramètres
    # ------------------------------------------------------------------

    def update_green_range(self):
        self.processor.update_green_range(
            self.hue_min.value(), self.hue_max.value(),
            self.sat_min.value(), self.val_min.value()
        )

    def update_morph_params(self):
        self.processor.update_morph_params(
            self.erode_slider.value(),
            self.dilate_slider.value(),
            self.smooth_slider.value()
        )

    def update_person_position(self):
        self.person_position_x = self.pos_x_slider.value()
        self.person_position_y = self.pos_y_slider.value()
        self.person_scale_z    = self.pos_z_slider.value() / 100.0
        self.pos_x_value.setText(str(self.person_position_x))
        self.pos_y_value.setText(str(self.person_position_y))
        self.pos_z_value.setText(f"{self.pos_z_slider.value()}%")

    def reset_position(self):
        """Remet X, Y et Z à zéro / 100%"""
        self.pos_x_slider.setValue(0)
        self.pos_y_slider.setValue(0)
        self.pos_z_slider.setValue(100)

    # ------------------------------------------------------------------
    # Prise de vue
    # ------------------------------------------------------------------

    def take_photo(self):
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

        self.capture_button.setEnabled(False)
        self.capture_button.setText("⏳ Traitement en cours...")
        QApplication.processEvents()

        try:
            assets_path = Path(__file__).parent / "assets"
            set_config = Config.SETS[self.current_set]
            fond_path = assets_path / set_config.fond_file
            pp_path   = assets_path / set_config.pp_file

            if not fond_path.exists():
                QMessageBox.critical(self, "Erreur", f"Fichier non trouvé: {fond_path}")
                return
            if not pp_path.exists():
                QMessageBox.critical(self, "Erreur", f"Fichier non trouvé: {pp_path}")
                return

            person_bgra, _ = self.processor.extract_person(self.current_frame)

            final_image = self.processor.composite_image(
                person_bgra, fond_path, pp_path,
                self.person_position_x, self.person_position_y,
                self.person_scale_z,
                self.zone_info, set_config
            )

            h, w = final_image.shape[:2]
            logger.info(f"Image finale: {w}x{h} px")

            filepath = self.processor.save_with_metadata(
                final_image, person_name, email, self.current_set
            )

            QMessageBox.information(self, "Succès",
                                    f"Photo sauvegardée :\n{filepath}\n"
                                    f"Dimensions : {w} x {h} pixels")

        except Exception as e:
            logger.error(f"Erreur take_photo: {e}")
            QMessageBox.critical(self, "Erreur", f"Erreur lors de la sauvegarde:\n{str(e)}")

        finally:
            self.capture_button.setEnabled(True)
            self.capture_button.setText("PRENDRE LA VUE")

    def closeEvent(self, event):
        """Fermeture propre : arrêter timers et thread avant de quitter."""
        self._progress_timer.stop()
        self.preview_timer.stop()
        self._safe_stop_thread()
        event.accept()


def main():
    app = QApplication(sys.argv)
    app.setStyle('Fusion')
    font = QFont("Arial", 9)
    app.setFont(font)
    window = MainWindow()
    window.show()
    sys.exit(app.exec_())


if __name__ == "__main__":
    main()