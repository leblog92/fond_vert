# main.py
import sys
import os
import logging
from pathlib import Path

from PyQt5.QtWidgets import (QApplication, QMainWindow, QWidget, QVBoxLayout,
                             QHBoxLayout, QPushButton, QComboBox, QLabel,
                             QGroupBox, QSlider, QSpinBox, QLineEdit,
                             QMessageBox, QGridLayout, QCheckBox, QProgressBar)
from PyQt5.QtCore import Qt, QTimer
from PyQt5.QtGui import QImage, QPixmap, QFont
import cv2
import numpy as np

from config import Config
from camera_manager import CameraThread, CameraScanner
from image_processor import GreenScreenProcessor
import settings as Settings

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)


class MainWindow(QMainWindow):
    def __init__(self):
        super().__init__()
        self.setWindowTitle("Studio Photo Fond Vert - Salon BD")
        self.setGeometry(100, 100, 1600, 900)

        # Paramètres persistants
        self._settings         = Settings.load()
        self.current_set       = self._settings["current_set"]
        self.camera_thread     = None
        self.processor         = GreenScreenProcessor()
        self.current_frame     = None
        self.person_position_x = self._settings["pos_x"]
        self.person_position_y = self._settings["pos_y"]
        self.person_scale_z    = self._settings["pos_z"] / 100.0
        self._camera_ready     = False
        self._show_mask        = self._settings["show_mask"]
        self._operator_mode    = False

        self._ui_cache = {}

        set_config = Config.SETS[self.current_set]
        self.zone_info = {
            'largeur': set_config.zone_largeur,
            'hauteur': set_config.zone_hauteur,
            'x':       set_config.zone_x,
            'y':       set_config.zone_y,
        }

        self.preview_timer = QTimer()
        self.preview_timer.timeout.connect(self.update_montage_preview)

        self._progress_timer = QTimer()
        self._progress_timer.setInterval(100)
        self._progress_timer.timeout.connect(self._tick_progress)
        self._progress_value = 0.0

        Config.ensure_save_dir()
        self.setup_ui()
        self._apply_settings_to_ui()
        self.scan_cameras()

    # ------------------------------------------------------------------
    # Cache UI
    # ------------------------------------------------------------------

    def _get_ui_assets(self, set_id):
        if set_id not in self._ui_cache:
            assets_path = Path(__file__).parent / "assets"
            cfg = Config.SETS[set_id]
            fond_path = assets_path / cfg.ui_fond_file
            pp_path   = assets_path / cfg.ui_pp_file
            if not fond_path.exists() or not pp_path.exists():
                return None, None
            bg = cv2.imread(str(fond_path))
            pp = cv2.imread(str(pp_path), cv2.IMREAD_UNCHANGED)
            if bg is None or pp is None:
                return None, None
            pp_bgra = cv2.cvtColor(pp, cv2.COLOR_BGR2BGRA) if pp.shape[2] == 3 else pp.copy()
            self._ui_cache[set_id] = (bg, pp_bgra)
        return self._ui_cache[set_id]

    # ------------------------------------------------------------------
    # Persistance
    # ------------------------------------------------------------------

    def _collect_settings(self):
        return {
            "hue_min":      self.hue_min.value(),
            "hue_max":      self.hue_max.value(),
            "sat_min":      self.sat_min.value(),
            "val_min":      self.val_min.value(),
            "erode":        self.erode_slider.value(),
            "dilate":       self.dilate_slider.value(),
            "smooth":       self.smooth_slider.value(),
            "pos_x":        self.pos_x_slider.value(),
            "pos_y":        self.pos_y_slider.value(),
            "pos_z":        self.pos_z_slider.value(),
            "current_set":  self.current_set,
            "show_mask":    self.mask_check.isChecked(),
            "live_preview": self.preview_check.isChecked(),
        }

    def _apply_settings_to_ui(self):
        s = self._settings
        widgets = [self.hue_min, self.hue_max, self.sat_min, self.val_min,
                   self.erode_slider, self.dilate_slider, self.smooth_slider,
                   self.pos_x_slider, self.pos_y_slider, self.pos_z_slider]
        for w in widgets:
            w.blockSignals(True)
        self.hue_min.setValue(s["hue_min"])
        self.hue_max.setValue(s["hue_max"])
        self.sat_min.setValue(s["sat_min"])
        self.val_min.setValue(s["val_min"])
        self.erode_slider.setValue(s["erode"])
        self.dilate_slider.setValue(s["dilate"])
        self.smooth_slider.setValue(s["smooth"])
        self.pos_x_slider.setValue(s["pos_x"])
        self.pos_y_slider.setValue(s["pos_y"])
        self.pos_z_slider.setValue(s["pos_z"])
        self.mask_check.setChecked(s["show_mask"])
        self.preview_check.setChecked(s["live_preview"])
        for w in widgets:
            w.blockSignals(False)
        self.set_combo.blockSignals(True)
        self.set_combo.setCurrentIndex(self.current_set - 1)
        self.set_combo.blockSignals(False)
        self.update_green_range()
        self.update_morph_params()
        self.update_person_position()
        self.update_set_info_display()

    # ------------------------------------------------------------------
    # Construction de l'UI
    # ------------------------------------------------------------------

    def setup_ui(self):
        central = QWidget()
        self.setCentralWidget(central)
        root = QHBoxLayout(central)
        root.setContentsMargins(6, 6, 6, 6)
        root.setSpacing(8)

        # ── Panneau gauche (technicien uniquement) ──
        self.left_panel = QWidget()
        left_layout = QVBoxLayout(self.left_panel)
        left_layout.setContentsMargins(0, 0, 0, 0)
        left_layout.addWidget(self._build_camera_group())

        self.camera_label = QLabel("Aperçu caméra")
        self.camera_label.setMinimumSize(400, 225)
        self.camera_label.setStyleSheet("border:2px solid #444; background:#2b2b2b;")
        self.camera_label.setAlignment(Qt.AlignCenter)
        left_layout.addWidget(self.camera_label)
        left_layout.addWidget(self._build_chroma_group())

        root.addWidget(self.left_panel, 2)

        # ── Panneau central (partagé) ──
        center = QWidget()
        center_layout = QVBoxLayout(center)
        center_layout.setContentsMargins(0, 0, 0, 0)

        preview_group = QGroupBox("Aperçu du montage en direct")
        preview_layout = QVBoxLayout()

        self.montage_label = QLabel("Aperçu du montage")
        self.montage_label.setMinimumSize(600, 400)
        self.montage_label.setStyleSheet("border:2px solid #4CAF50; background:#2b2b2b;")
        self.montage_label.setAlignment(Qt.AlignCenter)
        preview_layout.addWidget(self.montage_label, stretch=1)

        bar = QHBoxLayout()
        self.preview_check = QCheckBox("Aperçu en direct")
        self.preview_check.setChecked(True)
        self.preview_check.stateChanged.connect(self.toggle_live_preview)
        bar.addWidget(self.preview_check)
        bar.addStretch()

        # Bouton bascule mode — visible dans les deux modes
        self.mode_btn = QPushButton("🖥  Mode Opérateur  [F11]")
        self.mode_btn.setFixedHeight(30)
        self.mode_btn.clicked.connect(self.toggle_operator_mode)
        self.mode_btn.setStyleSheet("""
            QPushButton { background:#37474F; color:#ccc;
                          font-size:11px; border-radius:4px; padding:0 12px; }
            QPushButton:hover { background:#4CAF50; color:white; }
        """)
        bar.addWidget(self.mode_btn)
        preview_layout.addLayout(bar)
        preview_group.setLayout(preview_layout)
        center_layout.addWidget(preview_group)

        root.addWidget(center, 3)

        # ── Panneau droit ──
        self.right_panel = QWidget()
        right_layout = QVBoxLayout(self.right_panel)
        right_layout.setContentsMargins(0, 0, 0, 0)
        right_layout.addWidget(self._build_set_group())
        right_layout.addWidget(self._build_position_group())
        right_layout.addWidget(self._build_info_group())

        self.capture_button = QPushButton("PRENDRE LA VUE")
        self.capture_button.setStyleSheet("""
            QPushButton { background:#4CAF50; color:white; font-size:16px;
                          font-weight:bold; padding:15px; border-radius:5px; }
            QPushButton:hover    { background:#45a049; }
            QPushButton:disabled { background:#ccc; }
        """)
        self.capture_button.clicked.connect(self.take_photo)
        self.capture_button.setEnabled(False)
        right_layout.addWidget(self.capture_button)

        self.open_folder_btn = QPushButton("📂 Ouvrir le dossier de sauvegarde")
        self.open_folder_btn.clicked.connect(lambda: os.startfile(Config.SAVE_DIR))
        self.open_folder_btn.setStyleSheet("""
            QPushButton { background:#2196F3; color:white;
                          font-size:12px; padding:8px; border-radius:4px; }
            QPushButton:hover { background:#1976D2; }
        """)
        right_layout.addWidget(self.open_folder_btn)

        root.addWidget(self.right_panel, 2)

    # ── Groupes de widgets ──────────────────────────────────────────────

    def _build_camera_group(self):
        g = QGroupBox("Caméra")
        ly = QVBoxLayout(g)

        row1 = QHBoxLayout()
        self.camera_combo = QComboBox()
        self.camera_combo.setMinimumWidth(160)
        self.scan_button = QPushButton("Scanner")
        self.scan_button.clicked.connect(self.scan_cameras)
        row1.addWidget(QLabel("Caméra:"))
        row1.addWidget(self.camera_combo)
        row1.addWidget(self.scan_button)
        ly.addLayout(row1)

        row2 = QHBoxLayout()
        self.start_button = QPushButton("Démarrer")
        self.start_button.clicked.connect(self.start_camera)
        self.stop_button = QPushButton("Arrêter")
        self.stop_button.clicked.connect(self.stop_camera)
        self.stop_button.setEnabled(False)
        row2.addWidget(self.start_button)
        row2.addWidget(self.stop_button)
        ly.addLayout(row2)

        self.camera_progress = QProgressBar()
        self.camera_progress.setRange(0, 1000)
        self.camera_progress.setFormat("Initialisation...")
        self.camera_progress.setVisible(False)
        ly.addWidget(self.camera_progress)
        return g

    def _build_chroma_group(self):
        g = QGroupBox("Paramètres de détourage")
        ly = QGridLayout(g)

        ly.addWidget(QLabel("Teinte min:"), 0, 0)
        self.hue_min = QSpinBox(); self.hue_min.setRange(0, 180); self.hue_min.setValue(35)
        self.hue_min.valueChanged.connect(self.update_green_range)
        ly.addWidget(self.hue_min, 0, 1)

        ly.addWidget(QLabel("Teinte max:"), 0, 2)
        self.hue_max = QSpinBox(); self.hue_max.setRange(0, 180); self.hue_max.setValue(85)
        self.hue_max.valueChanged.connect(self.update_green_range)
        ly.addWidget(self.hue_max, 0, 3)

        ly.addWidget(QLabel("Sat. min:"), 1, 0)
        self.sat_min = QSpinBox(); self.sat_min.setRange(0, 255); self.sat_min.setValue(50)
        self.sat_min.valueChanged.connect(self.update_green_range)
        ly.addWidget(self.sat_min, 1, 1)

        ly.addWidget(QLabel("Lum. min:"), 1, 2)
        self.val_min = QSpinBox(); self.val_min.setRange(0, 255); self.val_min.setValue(50)
        self.val_min.valueChanged.connect(self.update_green_range)
        ly.addWidget(self.val_min, 1, 3)

        ly.addWidget(QLabel("Érosion:"), 2, 0)
        self.erode_slider = QSlider(Qt.Horizontal); self.erode_slider.setRange(0, 5); self.erode_slider.setValue(1)
        self.erode_slider.valueChanged.connect(self.update_morph_params)
        ly.addWidget(self.erode_slider, 2, 1)

        ly.addWidget(QLabel("Dilatation:"), 2, 2)
        self.dilate_slider = QSlider(Qt.Horizontal); self.dilate_slider.setRange(0, 5); self.dilate_slider.setValue(2)
        self.dilate_slider.valueChanged.connect(self.update_morph_params)
        ly.addWidget(self.dilate_slider, 2, 3)

        ly.addWidget(QLabel("Lissage:"), 3, 0)
        self.smooth_slider = QSlider(Qt.Horizontal); self.smooth_slider.setRange(1, 10); self.smooth_slider.setValue(5)
        self.smooth_slider.valueChanged.connect(self.update_morph_params)
        ly.addWidget(self.smooth_slider, 3, 1)

        self.mask_check = QCheckBox("Afficher le masque alpha")
        self.mask_check.setToolTip("Blanc = personne  |  Noir = fond supprimé")
        self.mask_check.stateChanged.connect(self.toggle_mask_view)
        ly.addWidget(self.mask_check, 4, 0, 1, 4)
        return g

    def _build_set_group(self):
        g = QGroupBox("Configuration du set")
        ly = QVBoxLayout(g)

        row = QHBoxLayout()
        row.addWidget(QLabel("Set:"))
        self.set_combo = QComboBox()
        for i in range(1, 5):
            self.set_combo.addItem(f"Set {i}")
        self.set_combo.currentIndexChanged.connect(self.change_set)
        row.addWidget(self.set_combo)
        ly.addLayout(row)

        self.set_info_label = QLabel("")
        self.set_info_label.setStyleSheet(
            "background:#f0f0f0; padding:5px; border-radius:3px; font-family:monospace;")
        self.set_info_label.setWordWrap(True)
        ly.addWidget(self.set_info_label)

        self.set_preview = QLabel("Aperçu du set")
        self.set_preview.setMinimumSize(280, 180)
        self.set_preview.setStyleSheet("border:1px solid black; background:#2b2b2b;")
        self.set_preview.setAlignment(Qt.AlignCenter)
        ly.addWidget(self.set_preview)
        return g

    def _build_position_group(self):
        g = QGroupBox("Position / Zoom")
        ly = QGridLayout(g)

        ly.addWidget(QLabel("X:"), 0, 0)
        self.pos_x_slider = QSlider(Qt.Horizontal); self.pos_x_slider.setRange(-500, 500)
        self.pos_x_slider.valueChanged.connect(self.update_person_position)
        ly.addWidget(self.pos_x_slider, 0, 1)
        self.pos_x_value = QLabel("0"); ly.addWidget(self.pos_x_value, 0, 2)

        ly.addWidget(QLabel("Y:"), 1, 0)
        self.pos_y_slider = QSlider(Qt.Horizontal); self.pos_y_slider.setRange(-500, 500)
        self.pos_y_slider.valueChanged.connect(self.update_person_position)
        ly.addWidget(self.pos_y_slider, 1, 1)
        self.pos_y_value = QLabel("0"); ly.addWidget(self.pos_y_value, 1, 2)

        ly.addWidget(QLabel("Z (zoom):"), 2, 0)
        self.pos_z_slider = QSlider(Qt.Horizontal)
        self.pos_z_slider.setRange(50, 200); self.pos_z_slider.setValue(100)
        self.pos_z_slider.valueChanged.connect(self.update_person_position)
        ly.addWidget(self.pos_z_slider, 2, 1)
        self.pos_z_value = QLabel("100%"); ly.addWidget(self.pos_z_value, 2, 2)

        reset_btn = QPushButton("Réinitialiser")
        reset_btn.clicked.connect(self.reset_position)
        ly.addWidget(reset_btn, 3, 0, 1, 3)
        return g

    def _build_info_group(self):
        g = QGroupBox("Informations personne")
        ly = QVBoxLayout(g)
        ly.addWidget(QLabel("Nom:"))
        self.name_input = QLineEdit(); self.name_input.setPlaceholderText("Ex: Jean Dupont")
        ly.addWidget(self.name_input)
        ly.addWidget(QLabel("Email:"))
        self.email_input = QLineEdit(); self.email_input.setPlaceholderText("exemple@email.com")
        ly.addWidget(self.email_input)
        return g

    # ------------------------------------------------------------------
    # Mode opérateur — simple show/hide + showFullScreen/showNormal
    # ------------------------------------------------------------------

    def toggle_operator_mode(self):
        """Bascule entre mode technicien et mode opérateur.
        Aucune fenêtre supplémentaire — on masque/affiche des panneaux."""
        self._operator_mode = not self._operator_mode

        if self._operator_mode:
            # Cacher les panneaux techniques
            self.left_panel.hide()
            # Réduire le panneau droit à l'essentiel
            self.set_info_label.hide()
            self._build_position_group   # les sliders restent cachés via right_panel
            # Cacher les widgets techniques du panneau droit
            for w in (self.set_info_label,):
                w.hide()
            # Passer en plein écran
            self.showFullScreen()
            self.mode_btn.setText("⚙  Mode Technicien  [F11]")
            self.mode_btn.setStyleSheet("""
                QPushButton { background:#4CAF50; color:white;
                              font-size:11px; border-radius:4px; padding:0 12px; }
                QPushButton:hover { background:#388E3C; }
            """)
            # Agrandir la police des champs pour l'opérateur
            for w in (self.name_input, self.email_input):
                w.setStyleSheet("font-size:18px; padding:8px;")
            self.capture_button.setStyleSheet("""
                QPushButton { background:#4CAF50; color:white; font-size:22px;
                              font-weight:bold; padding:20px; border-radius:6px; }
                QPushButton:hover    { background:#45a049; }
                QPushButton:disabled { background:#ccc; }
            """)
            self.set_combo.setStyleSheet("font-size:16px; padding:6px;")
        else:
            # Restaurer le mode technicien
            self.left_panel.show()
            self.set_info_label.show()
            self.showNormal()
            self.mode_btn.setText("🖥  Mode Opérateur  [F11]")
            self.mode_btn.setStyleSheet("""
                QPushButton { background:#37474F; color:#ccc;
                              font-size:11px; border-radius:4px; padding:0 12px; }
                QPushButton:hover { background:#4CAF50; color:white; }
            """)
            # Restaurer la police normale
            for w in (self.name_input, self.email_input):
                w.setStyleSheet("")
            self.capture_button.setStyleSheet("""
                QPushButton { background:#4CAF50; color:white; font-size:16px;
                              font-weight:bold; padding:15px; border-radius:5px; }
                QPushButton:hover    { background:#45a049; }
                QPushButton:disabled { background:#ccc; }
            """)
            self.set_combo.setStyleSheet("")

    def keyPressEvent(self, event):
        if event.key() == Qt.Key_F11:
            self.toggle_operator_mode()
        elif event.key() == Qt.Key_Escape and self._operator_mode:
            self.toggle_operator_mode()
        else:
            super().keyPressEvent(event)

    def update_set_info_display(self):
        set_config = Config.SETS[self.current_set]
        info_text = (f"📐 Set {self.current_set}\n"
                     f"└─ Fond: {set_config.largeur_fond} x {set_config.hauteur_fond} px\n"
                     f"└─ Zone: {set_config.zone_largeur} x {set_config.zone_hauteur} px\n"
                     f"└─ X={set_config.zone_x}, Y={set_config.zone_y}")
        if hasattr(self, 'set_info_label'):
            self.set_info_label.setText(info_text)

    # ------------------------------------------------------------------
    # Caméra
    # ------------------------------------------------------------------

    def scan_cameras(self):
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
        self._camera_ready   = False
        self._progress_value = 0.0
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
        if self._camera_ready:
            self.camera_progress.setValue(1000)
            self.camera_progress.setFormat("Caméra prête ✓")
            self._progress_timer.stop()
            QTimer.singleShot(800, lambda: self.camera_progress.setVisible(False))
        else:
            if self._progress_value < 900:
                self._progress_value += 3.6
                self.camera_progress.setValue(int(self._progress_value))

    def _safe_stop_thread(self):
        if self.camera_thread is None:
            return
        self.camera_thread.stop()
        if not self.camera_thread.wait(3000):
            self.camera_thread.terminate()
            self.camera_thread.wait(1000)
        self.camera_thread = None

    def stop_camera(self):
        self._progress_timer.stop()
        self.preview_timer.stop()
        self.camera_progress.setVisible(False)
        self._safe_stop_thread()
        self._camera_ready = False
        self.current_frame = None
        self.camera_label.clear(); self.camera_label.setText("Aperçu caméra")
        self.montage_label.clear(); self.montage_label.setText("Aperçu du montage")
        self.set_preview.clear();   self.set_preview.setText("Aperçu du set")
        self.start_button.setEnabled(True)
        self.stop_button.setEnabled(False)
        self.capture_button.setEnabled(False)

    def update_image(self, frame):
        self.current_frame = frame.copy()
        if not self._camera_ready:
            self._camera_ready = True
            self.update_set_preview()
            self.update_set_info_display()
        try:
            person_bgra, mask = self.processor.extract_person(frame)
            display = (cv2.cvtColor(mask, cv2.COLOR_GRAY2RGB) if self._show_mask
                       else cv2.cvtColor(person_bgra, cv2.COLOR_BGRA2RGB))
            h, w, ch = display.shape
            qt_img = QImage(display.tobytes(), w, h, ch * w, QImage.Format_RGB888)
            self.camera_label.setPixmap(
                QPixmap.fromImage(qt_img).scaled(
                    self.camera_label.size(), Qt.KeepAspectRatio, Qt.SmoothTransformation))
        except Exception as e:
            logger.error(f"Erreur update_image: {e}")

    def update_montage_preview(self):
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
                self.person_scale_z, set_config)
            if preview is not None and preview.size > 0:
                h, w, ch = preview.shape
                qt_img = QImage(preview.tobytes(), w, h, ch * w, QImage.Format_RGB888)
                self.montage_label.setPixmap(
                    QPixmap.fromImage(qt_img).scaled(
                        self.montage_label.size(), Qt.KeepAspectRatio, Qt.SmoothTransformation))
        except Exception as e:
            logger.error(f"Erreur update_montage_preview: {e}")

    def toggle_live_preview(self, state):
        if state == Qt.Checked and self.camera_thread is not None:
            self.preview_timer.start(200)
        else:
            self.preview_timer.stop()
            self.montage_label.clear()
            self.montage_label.setText("Aperçu du montage")

    def toggle_mask_view(self, state):
        self._show_mask = (state == Qt.Checked)
        self.camera_label.setStyleSheet(
            "border:2px solid #FF9800; background:#1a1a1a;" if self._show_mask
            else "border:2px solid #444; background:#2b2b2b;")

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
        if self._camera_ready:
            self.update_set_preview()
        set_config = Config.SETS[self.current_set]
        self.zone_info = {
            'largeur': set_config.zone_largeur, 'hauteur': set_config.zone_hauteur,
            'x': set_config.zone_x,             'y':       set_config.zone_y,
        }
        self.update_set_info_display()

    def update_set_preview(self):
        try:
            ui_bg, ui_pp = self._get_ui_assets(self.current_set)
            if ui_bg is None:
                self.set_preview.setText("Fichiers UI non trouvés"); return
            fond_small = ui_bg.copy()
            if ui_pp is not None and ui_pp.shape[2] == 4:
                ui_pp_r = (cv2.resize(ui_pp, (ui_bg.shape[1], ui_bg.shape[0]))
                           if ui_pp.shape[:2] != ui_bg.shape[:2] else ui_pp)
                a   = ui_pp_r[:, :, 3:4].astype(np.float32) / 255.0
                src = ui_pp_r[:, :, :3].astype(np.float32)
                dst = fond_small.astype(np.float32)
                fond_small = np.clip(a * src + (1 - a) * dst, 0, 255).astype(np.uint8)
            rgb = cv2.cvtColor(fond_small, cv2.COLOR_BGR2RGB)
            h, w, ch = rgb.shape
            qt_img = QImage(rgb.tobytes(), w, h, ch * w, QImage.Format_RGB888)
            self.set_preview.setPixmap(
                QPixmap.fromImage(qt_img).scaled(
                    self.set_preview.size(), Qt.KeepAspectRatio, Qt.SmoothTransformation))
        except Exception as e:
            logger.error(f"Erreur update_set_preview: {e}")
            self.set_preview.setText(f"Erreur: {e}")

    # ------------------------------------------------------------------
    # Paramètres
    # ------------------------------------------------------------------

    def update_green_range(self):
        self.processor.update_green_range(
            self.hue_min.value(), self.hue_max.value(),
            self.sat_min.value(), self.val_min.value())

    def update_morph_params(self):
        self.processor.update_morph_params(
            self.erode_slider.value(), self.dilate_slider.value(), self.smooth_slider.value())

    def update_person_position(self):
        self.person_position_x = self.pos_x_slider.value()
        self.person_position_y = self.pos_y_slider.value()
        self.person_scale_z    = self.pos_z_slider.value() / 100.0
        self.pos_x_value.setText(str(self.person_position_x))
        self.pos_y_value.setText(str(self.person_position_y))
        self.pos_z_value.setText(f"{self.pos_z_slider.value()}%")

    def reset_position(self):
        self.pos_x_slider.setValue(0)
        self.pos_y_slider.setValue(0)
        self.pos_z_slider.setValue(100)

    # ------------------------------------------------------------------
    # Prise de vue
    # ------------------------------------------------------------------

    def take_photo(self):
        if self.current_frame is None:
            QMessageBox.warning(self, "Erreur", "Aucune image disponible"); return
        person_name = self.name_input.text().strip()
        email       = self.email_input.text().strip()
        if not person_name:
            QMessageBox.warning(self, "Erreur", "Veuillez entrer un nom"); return
        if not email:
            QMessageBox.warning(self, "Erreur", "Veuillez entrer une adresse email"); return

        self.capture_button.setEnabled(False)
        self.capture_button.setText("⏳ Traitement en cours...")
        QApplication.processEvents()

        try:
            assets_path = Path(__file__).parent / "assets"
            set_config  = Config.SETS[self.current_set]
            fond_path   = assets_path / set_config.fond_file
            pp_path     = assets_path / set_config.pp_file
            if not fond_path.exists():
                QMessageBox.critical(self, "Erreur", f"Fichier non trouvé: {fond_path}"); return
            if not pp_path.exists():
                QMessageBox.critical(self, "Erreur", f"Fichier non trouvé: {pp_path}"); return

            person_bgra, _ = self.processor.extract_person(self.current_frame)
            final_image = self.processor.composite_image(
                person_bgra, fond_path, pp_path,
                self.person_position_x, self.person_position_y,
                self.person_scale_z, self.zone_info, set_config)

            h, w = final_image.shape[:2]
            filepath = self.processor.save_with_metadata(
                final_image, person_name, email, self.current_set)

            QMessageBox.information(self, "Succès",
                                    f"Photo sauvegardée :\n{filepath}\n"
                                    f"Dimensions : {w} x {h} pixels")
        except Exception as e:
            logger.error(f"Erreur take_photo: {e}")
            QMessageBox.critical(self, "Erreur", f"Erreur :\n{str(e)}")
        finally:
            self.capture_button.setEnabled(True)
            self.capture_button.setText("PRENDRE LA VUE")

    # ------------------------------------------------------------------
    # Fermeture
    # ------------------------------------------------------------------

    def closeEvent(self, event):
        Settings.save(self._collect_settings())
        self._progress_timer.stop()
        self.preview_timer.stop()
        self._safe_stop_thread()
        event.accept()


def main():
    app = QApplication(sys.argv)
    app.setStyle('Fusion')
    app.setFont(QFont("Arial", 9))
    window = MainWindow()
    window.show()
    sys.exit(app.exec_())


if __name__ == "__main__":
    main()
