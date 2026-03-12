import tkinter as tk
from tkinter import ttk, messagebox, filedialog
import cv2
from PIL import Image, ImageTk
import numpy as np
import os
from pathlib import Path
import threading
import time
from dataclasses import dataclass
import json
import sys

@dataclass
class SetConfig:
    """Configuration pour chaque set (fond + premier plan)"""
    fond_file: str
    pp_file: str
    largeur: int
    hauteur: int
    zone_visible: tuple  # (largeur, hauteur, pos_x, pos_y)

class GreenScreenConfig:
    """Configuration pour le détourage fond vert"""
    def __init__(self):
        self.hue_min = tk.IntVar(value=35)
        self.hue_max = tk.IntVar(value=85)
        self.sat_min = tk.IntVar(value=40)
        self.val_min = tk.IntVar(value=40)
        self.erosion = tk.IntVar(value=1)
        self.dilation = tk.IntVar(value=1)
        self.blur = tk.IntVar(value=3)
        self.edge_threshold = tk.DoubleVar(value=0.5)
        self.matting_strength = tk.DoubleVar(value=0.3)

class CameraAdapter:
    """Gère l'adaptation des différentes proportions de caméra"""
    
    # Format cible
    TARGET_WIDTH = 1932
    TARGET_HEIGHT = 2576
    TARGET_ASPECT = TARGET_WIDTH / TARGET_HEIGHT  # ~0.75
    
    def __init__(self):
        self.camera_width = None
        self.camera_height = None
        self.camera_aspect = None
        
    def set_camera_dimensions(self, width, height):
        """Enregistre les dimensions de la caméra"""
        self.camera_width = width
        self.camera_height = height
        self.camera_aspect = width / height if height > 0 else 0
        print(f"Caméra détectée: {width}x{height} (ratio: {self.camera_aspect:.3f})")
        
    def get_adaptation_method(self):
        """Détermine la méthode d'adaptation nécessaire"""
        if self.camera_aspect is None:
            return "unknown"
            
        target_aspect = self.TARGET_ASPECT
        
        if abs(self.camera_aspect - target_aspect) < 0.01:
            return "exact_match"
        elif self.camera_aspect > target_aspect:
            return "wider_than_target"  # Caméra plus large
        else:
            return "taller_than_target"  # Caméra plus haute
    
    def adapt_frame_to_target(self, frame):
        """Adapte le frame de la caméra au format cible"""
        if frame is None:
            return None
            
        h, w = frame.shape[:2]
        method = self.get_adaptation_method()
        
        if method == "exact_match":
            # Déjà au bon format
            return cv2.resize(frame, (self.TARGET_WIDTH, self.TARGET_HEIGHT))
            
        elif method == "wider_than_target":
            # Caméra plus large: on recadre horizontalement
            target_h = self.TARGET_HEIGHT
            target_w = self.TARGET_WIDTH
            
            # Calculer le facteur d'échelle pour la hauteur
            scale = target_h / h
            new_w = int(w * scale)
            
            # Redimensionner pour que la hauteur corresponde
            resized = cv2.resize(frame, (new_w, target_h))
            
            # Recadrer au centre pour obtenir la largeur cible
            start_x = (new_w - target_w) // 2
            if start_x < 0:
                start_x = 0
            cropped = resized[:, start_x:start_x + target_w]
            
            # Si le recadrage a réduit la largeur, redimensionner
            if cropped.shape[1] != target_w:
                cropped = cv2.resize(cropped, (target_w, target_h))
                
            return cropped
            
        elif method == "taller_than_target":
            # Caméra plus haute: on recadre verticalement
            target_h = self.TARGET_HEIGHT
            target_w = self.TARGET_WIDTH
            
            # Calculer le facteur d'échelle pour la largeur
            scale = target_w / w
            new_h = int(h * scale)
            
            # Redimensionner pour que la largeur corresponde
            resized = cv2.resize(frame, (target_w, new_h))
            
            # Recadrer au centre pour obtenir la hauteur cible
            start_y = (new_h - target_h) // 2
            if start_y < 0:
                start_y = 0
            cropped = resized[start_y:start_y + target_h, :]
            
            # Si le recadrage a réduit la hauteur, redimensionner
            if cropped.shape[0] != target_h:
                cropped = cv2.resize(cropped, (target_w, target_h))
                
            return cropped
            
        else:
            # Méthode inconnue: redimensionnement simple
            return cv2.resize(frame, (self.TARGET_WIDTH, self.TARGET_HEIGHT))
    
    def get_adaptation_info(self):
        """Retourne des informations sur l'adaptation"""
        if self.camera_aspect is None:
            return "Caméra non détectée"
            
        method = self.get_adaptation_method()
        infos = {
            "exact_match": "Format parfait - aucun ajustement",
            "wider_than_target": "Caméra plus large - recadrage horizontal",
            "taller_than_target": "Caméra plus haute - recadrage vertical",
            "unknown": "Format inconnu"
        }
        
        return f"Format caméra: {self.camera_width}x{self.camera_height} (ratio: {self.camera_aspect:.3f})\nMéthode: {infos.get(method, 'Adaptation standard')}"

class SalonBDApp:
    def __init__(self, root):
        self.root = root
        self.root.title("Salon BD - Photomaton (Adaptatif)")
        self.root.geometry("1600x900")
        
        # Configuration des dossiers
        self.images_dir = Path(__file__).parent / "images"
        self.output_dir = Path(os.environ['USERPROFILE']) / "Pictures" / "SalonBD"
        self.output_dir.mkdir(parents=True, exist_ok=True)
        
        # Adaptateur de caméra
        self.camera_adapter = CameraAdapter()
        
        # Charger la configuration
        self.load_config()
        
        # Configuration des sets
        self.sets = {
            "set 1": SetConfig("fond1.png", "pp1.png", 2000, 1688, (900, 591, 1, 961)),
            "set 2": SetConfig("fond2.png", "pp2.png", 2000, 1414, (1960, 1270, 14, 78)),
            "set 3": SetConfig("fond3.png", "pp3.png", 2000, 2632, (437, 702, 1361, 1712))
        }
        
        # Variables d'état
        self.current_set = tk.StringVar(value="set 1")
        self.camera_running = False
        self.camera = None
        self.camera_index = tk.IntVar(value=1)
        self.available_cameras = []
        self.adjust_x = tk.DoubleVar(value=0)
        self.adjust_y = tk.DoubleVar(value=0)
        self.zoom_factor = tk.DoubleVar(value=1.0)
        self.preview_active = False
        self.green_config = GreenScreenConfig()
        self.adaptation_mode = tk.StringVar(value="auto")  # auto, crop, stretch, pad
        
        # Charger les images de fond et premier plan
        self.load_backgrounds()
        
        # Initialiser l'interface
        self.setup_ui()
        
        # Scanner les caméras disponibles
        self.scan_cameras()
        
        # Mettre à jour les informations du set
        self.update_set_info()
    
    def load_config(self):
        """Charge la configuration depuis le fichier JSON"""
        config_file = Path(__file__).parent / "config.json"
        if config_file.exists():
            try:
                with open(config_file, 'r') as f:
                    self.config = json.load(f)
            except:
                self.config = self.get_default_config()
        else:
            self.config = self.get_default_config()
            self.save_config()
    
    def get_default_config(self):
        """Retourne la configuration par défaut"""
        return {
            "camera_settings": {
                "width": 1932,
                "height": 2576,
                "default_device_index": 1
            },
            "green_screen": {
                "lower_hue": 35,
                "upper_hue": 85,
                "lower_saturation": 40,
                "upper_saturation": 255,
                "lower_value": 40,
                "upper_value": 255
            },
            "matting": {
                "erosion": 1,
                "dilation": 1,
                "blur": 3,
                "edge_threshold": 0.5,
                "matting_strength": 0.3
            }
        }
    
    def save_config(self):
        """Sauvegarde la configuration"""
        config_file = Path(__file__).parent / "config.json"
        with open(config_file, 'w') as f:
            json.dump(self.config, f, indent=4)
    
    def load_backgrounds(self):
        """Charge les images de fond et premier plan"""
        self.fonds = {}
        self.pps = {}
        
        for set_name, config in self.sets.items():
            fond_path = self.images_dir / config.fond_file
            pp_path = self.images_dir / config.pp_file
            
            if fond_path.exists():
                img = cv2.imread(str(fond_path))
                if img is not None:
                    self.fonds[set_name] = cv2.cvtColor(img, cv2.COLOR_BGR2RGB)
                else:
                    print(f"Impossible de charger: {fond_path}")
            else:
                print(f"Fichier non trouvé: {fond_path}")
                
            if pp_path.exists():
                img = cv2.imread(str(pp_path), cv2.IMREAD_UNCHANGED)
                if img is not None:
                    if img.shape[2] == 3:
                        img = cv2.cvtColor(img, cv2.COLOR_BGR2RGB)
                    else:
                        img = cv2.cvtColor(img, cv2.COLOR_BGRA2RGBA)
                    self.pps[set_name] = img
                else:
                    print(f"Impossible de charger: {pp_path}")
            else:
                print(f"Fichier non trouvé: {pp_path}")
    
    def scan_cameras(self):
        """Scanne les caméras disponibles"""
        self.available_cameras = []
        for i in range(5):  # Tester les 5 premiers indices
            cap = cv2.VideoCapture(i)
            if cap.isOpened():
                ret, frame = cap.read()
                if ret:
                    self.available_cameras.append(i)
                cap.release()
        
        # Mettre à jour le menu déroulant
        if hasattr(self, 'camera_combo'):
            self.camera_combo['values'] = self.available_cameras if self.available_cameras else ["Aucune"]
            if self.available_cameras:
                self.camera_index.set(self.available_cameras[0])
            else:
                self.camera_index.set("Aucune")
    
    def setup_ui(self):
        """Configure l'interface utilisateur"""
        # Configuration du redimensionnement
        self.root.columnconfigure(0, weight=1)
        self.root.rowconfigure(0, weight=1)
        
        # Frame principal avec onglets
        self.notebook = ttk.Notebook(self.root)
        self.notebook.grid(row=0, column=0, sticky=(tk.W, tk.E, tk.N, tk.S))
        
        # Onglet principal
        main_tab = ttk.Frame(self.notebook)
        self.notebook.add(main_tab, text="Photomaton")
        
        # Onglet paramètres avancés
        settings_tab = ttk.Frame(self.notebook)
        self.notebook.add(settings_tab, text="Paramètres avancés")
        
        self.setup_main_tab(main_tab)
        self.setup_settings_tab(settings_tab)
    
    def setup_main_tab(self, parent):
        """Configure l'onglet principal"""
        # Configuration du grid
        parent.columnconfigure(1, weight=1)
        parent.rowconfigure(0, weight=1)
        
        # Panneau de contrôle gauche
        control_frame = ttk.LabelFrame(parent, text="Contrôles", padding="10")
        control_frame.grid(row=0, column=0, sticky=(tk.W, tk.E, tk.N, tk.S), padx=(0, 10))
        
        # Gestion de la caméra
        camera_frame = ttk.LabelFrame(control_frame, text="Caméra", padding="5")
        camera_frame.grid(row=0, column=0, columnspan=2, sticky=(tk.W, tk.E), pady=5)
        
        # Sélection de la caméra
        ttk.Label(camera_frame, text="Caméra:").grid(row=0, column=0, sticky=tk.W, pady=2)
        self.camera_combo = ttk.Combobox(camera_frame, textvariable=self.camera_index, 
                                        values=[], state="readonly", width=10)
        self.camera_combo.grid(row=0, column=1, sticky=(tk.W, tk.E), pady=2, padx=(5, 0))
        
        # Boutons caméra
        btn_frame = ttk.Frame(camera_frame)
        btn_frame.grid(row=1, column=0, columnspan=2, pady=5)
        
        self.start_cam_btn = ttk.Button(btn_frame, text="▶ Démarrer", 
                                        command=self.start_camera, width=12)
        self.start_cam_btn.grid(row=0, column=0, padx=2)
        
        self.stop_cam_btn = ttk.Button(btn_frame, text="■ Arrêter", 
                                       command=self.stop_camera, width=12, state=tk.DISABLED)
        self.stop_cam_btn.grid(row=0, column=1, padx=2)
        
        ttk.Button(btn_frame, text="↻ Scanner", command=self.scan_cameras, width=12).grid(row=0, column=2, padx=2)
        
        # Informations caméra
        self.camera_info_label = ttk.Label(camera_frame, text="Format: Non détecté", foreground="blue")
        self.camera_info_label.grid(row=2, column=0, columnspan=2, pady=2)
        
        # Sélection du mode d'adaptation
        adapt_frame = ttk.LabelFrame(control_frame, text="Adaptation format", padding="5")
        adapt_frame.grid(row=1, column=0, columnspan=2, sticky=(tk.W, tk.E), pady=5)
        
        ttk.Radiobutton(adapt_frame, text="Auto (recommandé)", variable=self.adaptation_mode, 
                       value="auto", command=self.update_preview).grid(row=0, column=0, sticky=tk.W)
        ttk.Radiobutton(adapt_frame, text="Recadrage", variable=self.adaptation_mode, 
                       value="crop", command=self.update_preview).grid(row=1, column=0, sticky=tk.W)
        ttk.Radiobutton(adapt_frame, text="Étirement", variable=self.adaptation_mode, 
                       value="stretch", command=self.update_preview).grid(row=2, column=0, sticky=tk.W)
        ttk.Radiobutton(adapt_frame, text="Lettres noires", variable=self.adaptation_mode, 
                       value="pad", command=self.update_preview).grid(row=3, column=0, sticky=tk.W)
        
        # Sélection du set
        set_frame = ttk.LabelFrame(control_frame, text="Set", padding="5")
        set_frame.grid(row=2, column=0, columnspan=2, sticky=(tk.W, tk.E), pady=5)
        
        ttk.Label(set_frame, text="Sélection:").grid(row=0, column=0, sticky=tk.W, pady=2)
        set_combo = ttk.Combobox(set_frame, textvariable=self.current_set, 
                                 values=list(self.sets.keys()), state="readonly")
        set_combo.grid(row=0, column=1, sticky=(tk.W, tk.E), pady=2, padx=(5, 0))
        set_combo.bind('<<ComboboxSelected>>', self.on_set_change)
        
        # Bouton changer de set
        ttk.Button(set_frame, text="Changer de set", command=self.on_set_change).grid(row=1, column=0, columnspan=2, pady=5)
        
        # Ajustements position
        position_frame = ttk.LabelFrame(control_frame, text="Ajustement position", padding="5")
        position_frame.grid(row=3, column=0, columnspan=2, sticky=(tk.W, tk.E), pady=5)
        
        ttk.Label(position_frame, text="X:").grid(row=0, column=0, sticky=tk.W, pady=2)
        x_scale = ttk.Scale(position_frame, from_=-200, to=200, orient=tk.HORIZONTAL,
                           variable=self.adjust_x, command=self.update_preview)
        x_scale.grid(row=0, column=1, sticky=(tk.W, tk.E), pady=2, padx=(5, 0))
        
        ttk.Label(position_frame, text="Y:").grid(row=1, column=0, sticky=tk.W, pady=2)
        y_scale = ttk.Scale(position_frame, from_=-200, to=200, orient=tk.HORIZONTAL,
                           variable=self.adjust_y, command=self.update_preview)
        y_scale.grid(row=1, column=1, sticky=(tk.W, tk.E), pady=2, padx=(5, 0))
        
        # Zoom
        ttk.Label(position_frame, text="Zoom:").grid(row=2, column=0, sticky=tk.W, pady=2)
        zoom_scale = ttk.Scale(position_frame, from_=0.5, to=2.0, orient=tk.HORIZONTAL,
                              variable=self.zoom_factor, command=self.update_preview)
        zoom_scale.grid(row=2, column=1, sticky=(tk.W, tk.E), pady=2, padx=(5, 0))
        
        # Bouton de capture
        ttk.Button(control_frame, text="📸 Prendre la photo", 
                  command=self.capture_photo, style="Big.TButton").grid(row=4, column=0, columnspan=2, pady=10)
        
        # Informations set
        self.info_text = tk.Text(control_frame, height=8, width=35, state=tk.DISABLED)
        self.info_text.grid(row=5, column=0, columnspan=2, pady=5)
        
        # Frame pour l'aperçu
        preview_frame = ttk.LabelFrame(parent, text="Aperçu", padding="10")
        preview_frame.grid(row=0, column=1, sticky=(tk.W, tk.E, tk.N, tk.S), padx=(0, 10))
        preview_frame.columnconfigure(0, weight=1)
        preview_frame.rowconfigure(0, weight=1)
        
        # Canvas pour l'aperçu avec ascenseurs
        canvas_frame = ttk.Frame(preview_frame)
        canvas_frame.grid(row=0, column=0, sticky=(tk.W, tk.E, tk.N, tk.S))
        canvas_frame.columnconfigure(0, weight=1)
        canvas_frame.rowconfigure(0, weight=1)
        
        self.h_scrollbar = ttk.Scrollbar(canvas_frame, orient=tk.HORIZONTAL)
        self.v_scrollbar = ttk.Scrollbar(canvas_frame, orient=tk.VERTICAL)
        
        self.preview_canvas = tk.Canvas(canvas_frame, width=800, height=600, bg='gray',
                                       xscrollcommand=self.h_scrollbar.set,
                                       yscrollcommand=self.v_scrollbar.set)
        
        self.h_scrollbar.config(command=self.preview_canvas.xview)
        self.v_scrollbar.config(command=self.preview_canvas.yview)
        
        self.preview_canvas.grid(row=0, column=0, sticky=(tk.W, tk.E, tk.N, tk.S))
        self.h_scrollbar.grid(row=1, column=0, sticky=(tk.W, tk.E))
        self.v_scrollbar.grid(row=0, column=1, sticky=(tk.N, tk.S))
        
        # Label pour l'image de la caméra brute
        camera_frame_view = ttk.LabelFrame(parent, text="Caméra", padding="10")
        camera_frame_view.grid(row=0, column=2, sticky=(tk.W, tk.E, tk.N, tk.S))
        
        self.camera_label = ttk.Label(camera_frame_view)
        self.camera_label.grid(row=0, column=0)
        
        # Statut
        self.status_label = ttk.Label(parent, text="Statut: Prêt", relief=tk.SUNKEN)
        self.status_label.grid(row=1, column=0, columnspan=3, sticky=(tk.W, tk.E), pady=5)
    
    def setup_settings_tab(self, parent):
        """Configure l'onglet des paramètres avancés"""
        # Configuration du grid
        parent.columnconfigure(0, weight=1)
        parent.rowconfigure(0, weight=1)
        
        # Notebook pour les sous-onglets
        settings_notebook = ttk.Notebook(parent)
        settings_notebook.grid(row=0, column=0, sticky=(tk.W, tk.E, tk.N, tk.S))
        
        # Onglet fond vert
        greenscreen_tab = ttk.Frame(settings_notebook)
        settings_notebook.add(greenscreen_tab, text="Fond vert")
        
        # Onglet détourage fin
        matting_tab = ttk.Frame(settings_notebook)
        settings_notebook.add(matting_tab, text="Détourage fin")
        
        # Onglet contours
        edge_tab = ttk.Frame(settings_notebook)
        settings_notebook.add(edge_tab, text="Contours")
        
        # Onglet sauvegarde
        save_tab = ttk.Frame(settings_notebook)
        settings_notebook.add(save_tab, text="Sauvegarde")
        
        self.setup_greenscreen_tab(greenscreen_tab)
        self.setup_matting_tab(matting_tab)
        self.setup_edge_tab(edge_tab)
        self.setup_save_tab(save_tab)
    
    def setup_greenscreen_tab(self, parent):
        """Configure les paramètres du fond vert"""
        frame = ttk.LabelFrame(parent, text="Paramètres de détection du vert", padding="10")
        frame.grid(row=0, column=0, sticky=(tk.W, tk.E, tk.N, tk.S), padx=10, pady=10)
        
        # Teinte min
        ttk.Label(frame, text="Teinte min (H):").grid(row=0, column=0, sticky=tk.W, pady=5)
        h_min_scale = ttk.Scale(frame, from_=0, to=179, orient=tk.HORIZONTAL,
                                variable=self.green_config.hue_min, command=self.update_preview)
        h_min_scale.grid(row=0, column=1, sticky=(tk.W, tk.E), pady=5, padx=(5, 0))
        ttk.Label(frame, textvariable=self.green_config.hue_min).grid(row=0, column=2, padx=5)
        
        # Teinte max
        ttk.Label(frame, text="Teinte max (H):").grid(row=1, column=0, sticky=tk.W, pady=5)
        h_max_scale = ttk.Scale(frame, from_=0, to=179, orient=tk.HORIZONTAL,
                                variable=self.green_config.hue_max, command=self.update_preview)
        h_max_scale.grid(row=1, column=1, sticky=(tk.W, tk.E), pady=5, padx=(5, 0))
        ttk.Label(frame, textvariable=self.green_config.hue_max).grid(row=1, column=2, padx=5)
        
        # Saturation min
        ttk.Label(frame, text="Saturation min (S):").grid(row=2, column=0, sticky=tk.W, pady=5)
        s_min_scale = ttk.Scale(frame, from_=0, to=255, orient=tk.HORIZONTAL,
                                variable=self.green_config.sat_min, command=self.update_preview)
        s_min_scale.grid(row=2, column=1, sticky=(tk.W, tk.E), pady=5, padx=(5, 0))
        ttk.Label(frame, textvariable=self.green_config.sat_min).grid(row=2, column=2, padx=5)
        
        # Valeur (luminosité) min
        ttk.Label(frame, text="Luminosité min (V):").grid(row=3, column=0, sticky=tk.W, pady=5)
        v_min_scale = ttk.Scale(frame, from_=0, to=255, orient=tk.HORIZONTAL,
                                variable=self.green_config.val_min, command=self.update_preview)
        v_min_scale.grid(row=3, column=1, sticky=(tk.W, tk.E), pady=5, padx=(5, 0))
        ttk.Label(frame, textvariable=self.green_config.val_min).grid(row=3, column=2, padx=5)
        
        # Bouton de réinitialisation
        ttk.Button(frame, text="Réinitialiser", command=self.reset_greenscreen).grid(row=4, column=0, columnspan=3, pady=10)
    
    def setup_matting_tab(self, parent):
        """Configure les paramètres de détourage fin"""
        frame = ttk.LabelFrame(parent, text="Paramètres de détourage", padding="10")
        frame.grid(row=0, column=0, sticky=(tk.W, tk.E, tk.N, tk.S), padx=10, pady=10)
        
        # Érosion
        ttk.Label(frame, text="Érosion:").grid(row=0, column=0, sticky=tk.W, pady=5)
        erosion_scale = ttk.Scale(frame, from_=0, to=10, orient=tk.HORIZONTAL,
                                  variable=self.green_config.erosion, command=self.update_preview)
        erosion_scale.grid(row=0, column=1, sticky=(tk.W, tk.E), pady=5, padx=(5, 0))
        ttk.Label(frame, textvariable=self.green_config.erosion).grid(row=0, column=2, padx=5)
        
        # Dilatation
        ttk.Label(frame, text="Dilatation:").grid(row=1, column=0, sticky=tk.W, pady=5)
        dilation_scale = ttk.Scale(frame, from_=0, to=10, orient=tk.HORIZONTAL,
                                   variable=self.green_config.dilation, command=self.update_preview)
        dilation_scale.grid(row=1, column=1, sticky=(tk.W, tk.E), pady=5, padx=(5, 0))
        ttk.Label(frame, textvariable=self.green_config.dilation).grid(row=1, column=2, padx=5)
        
        # Flou des bords
        ttk.Label(frame, text="Flou des bords:").grid(row=2, column=0, sticky=tk.W, pady=5)
        blur_scale = ttk.Scale(frame, from_=1, to=21, orient=tk.HORIZONTAL,
                               variable=self.green_config.blur, command=self.update_preview)
        blur_scale.grid(row=2, column=1, sticky=(tk.W, tk.E), pady=5, padx=(5, 0))
        ttk.Label(frame, textvariable=self.green_config.blur).grid(row=2, column=2, padx=5)
        
        # Note
        ttk.Label(frame, text="Note: Le flou doit être un nombre impair").grid(row=3, column=0, columnspan=3, pady=10)
    
    def setup_edge_tab(self, parent):
        """Configure les paramètres de contours"""
        frame = ttk.LabelFrame(parent, text="Paramètres des contours", padding="10")
        frame.grid(row=0, column=0, sticky=(tk.W, tk.E, tk.N, tk.S), padx=10, pady=10)
        
        # Seuil de transparence
        ttk.Label(frame, text="Seuil de transparence:").grid(row=0, column=0, sticky=tk.W, pady=5)
        edge_scale = ttk.Scale(frame, from_=0.0, to=1.0, orient=tk.HORIZONTAL,
                               variable=self.green_config.edge_threshold, 
                               command=self.update_preview)
        edge_scale.grid(row=0, column=1, sticky=(tk.W, tk.E), pady=5, padx=(5, 0))
        ttk.Label(frame, textvariable=self.green_config.edge_threshold).grid(row=0, column=2, padx=5)
        
        # Force du matting
        ttk.Label(frame, text="Force du matting:").grid(row=1, column=0, sticky=tk.W, pady=5)
        matting_scale = ttk.Scale(frame, from_=0.0, to=1.0, orient=tk.HORIZONTAL,
                                  variable=self.green_config.matting_strength,
                                  command=self.update_preview)
        matting_scale.grid(row=1, column=1, sticky=(tk.W, tk.E), pady=5, padx=(5, 0))
        ttk.Label(frame, textvariable=self.green_config.matting_strength).grid(row=1, column=2, padx=5)
    
    def setup_save_tab(self, parent):
        """Configure les paramètres de sauvegarde"""
        frame = ttk.LabelFrame(parent, text="Paramètres de sauvegarde", padding="10")
        frame.grid(row=0, column=0, sticky=(tk.W, tk.E, tk.N, tk.S), padx=10, pady=10)
        
        # Dossier de sauvegarde
        ttk.Label(frame, text="Dossier de sauvegarde:").grid(row=0, column=0, sticky=tk.W, pady=5)
        self.save_path_label = ttk.Label(frame, text=str(self.output_dir), wraplength=300)
        self.save_path_label.grid(row=1, column=0, columnspan=2, sticky=tk.W, pady=5)
        
        ttk.Button(frame, text="Changer dossier", command=self.change_save_folder).grid(row=2, column=0, pady=5)
        
        # Format de fichier
        ttk.Label(frame, text="Format:").grid(row=3, column=0, sticky=tk.W, pady=5)
        self.file_format = tk.StringVar(value="PNG")
        format_combo = ttk.Combobox(frame, textvariable=self.file_format,
                                    values=["PNG", "JPG", "TIFF"], state="readonly")
        format_combo.grid(row=3, column=1, sticky=tk.W, pady=5)
    
    def reset_greenscreen(self):
        """Réinitialise les paramètres du fond vert"""
        self.green_config.hue_min.set(35)
        self.green_config.hue_max.set(85)
        self.green_config.sat_min.set(40)
        self.green_config.val_min.set(40)
        self.green_config.erosion.set(1)
        self.green_config.dilation.set(1)
        self.green_config.blur.set(3)
        self.green_config.edge_threshold.set(0.5)
        self.green_config.matting_strength.set(0.3)
        self.update_preview()
    
    def change_save_folder(self):
        """Change le dossier de sauvegarde"""
        folder = filedialog.askdirectory(initialdir=self.output_dir)
        if folder:
            self.output_dir = Path(folder)
            self.save_path_label.config(text=str(self.output_dir))
    
    def update_set_info(self):
        """Met à jour les informations du set sélectionné"""
        config = self.sets[self.current_set.get()]
        info = f"Set: {self.current_set.get()}\n"
        info += f"Fond: {config.fond_file}\n"
        info += f"Premier plan: {config.pp_file}\n"
        info += f"Dimensions décor: {config.largeur}x{config.hauteur}\n"
        info += f"Zone visible: {config.zone_visible[0]}x{config.zone_visible[1]}\n"
        info += f"Position zone: ({config.zone_visible[2]}, {config.zone_visible[3]})"
        
        self.info_text.config(state=tk.NORMAL)
        self.info_text.delete(1.0, tk.END)
        self.info_text.insert(1.0, info)
        self.info_text.config(state=tk.DISABLED)
    
    def on_set_change(self, event=None):
        """Appelé quand le set change"""
        self.update_set_info()
        self.update_preview()
    
    def start_camera(self):
        """Démarre la caméra sélectionnée"""
        if not self.available_cameras:
            messagebox.showerror("Erreur", "Aucune caméra détectée!\n\n"
                                 "Vérifiez que:\n"
                                 "- Iriun est installé et lancé\n"
                                 "- La tablette est connectée au même WiFi\n"
                                 "- Les pilotes sont correctement installés")
            return
        
        try:
            camera_idx = int(self.camera_index.get())
        except:
            messagebox.showerror("Erreur", "Sélectionnez une caméra valide")
            return
        
        if self.camera_running:
            self.stop_camera()
        
        self.camera = cv2.VideoCapture(camera_idx)
        
        if self.camera.isOpened():
            # Obtenir les dimensions réelles de la caméra
            width = int(self.camera.get(cv2.CAP_PROP_FRAME_WIDTH))
            height = int(self.camera.get(cv2.CAP_PROP_FRAME_HEIGHT))
            
            # Mettre à jour l'adaptateur
            self.camera_adapter.set_camera_dimensions(width, height)
            
            # Mettre à jour l'affichage des informations
            self.camera_info_label.config(
                text=self.camera_adapter.get_adaptation_info(),
                foreground="green" if width > 0 else "red"
            )
            
            self.camera_running = True
            self.preview_active = True
            
            # Mettre à jour l'interface
            self.start_cam_btn.config(state=tk.DISABLED)
            self.stop_cam_btn.config(state=tk.NORMAL)
            self.status_label.config(text=f"Statut: Caméra {camera_idx} active ({width}x{height})")
            
            # Démarrer la mise à jour
            self.update_camera()
        else:
            messagebox.showerror("Erreur", f"Impossible d'ouvrir la caméra {camera_idx}")
    
    def stop_camera(self):
        """Arrête la caméra"""
        self.camera_running = False
        self.preview_active = False
        
        if self.camera:
            self.camera.release()
            self.camera = None
        
        # Mettre à jour l'interface
        self.start_cam_btn.config(state=tk.NORMAL)
        self.stop_cam_btn.config(state=tk.DISABLED)
        self.status_label.config(text="Statut: Caméra arrêtée")
        self.camera_info_label.config(text="Format: Non détecté", foreground="blue")
        
        # Nettoyer l'affichage
        self.camera_label.config(image='')
        self.preview_canvas.delete("all")
    
    def update_camera(self):
        """Met à jour l'affichage de la caméra"""
        if self.camera_running and self.camera:
            ret, frame = self.camera.read()
            if ret:
                # Adapter le frame au format cible
                adapted_frame = self.adapt_camera_frame(frame)
                
                # Redimensionner pour l'affichage
                frame_resized = cv2.resize(adapted_frame, (400, 533))
                frame_rgb = cv2.cvtColor(frame_resized, cv2.COLOR_BGR2RGB)
                
                # Convertir en ImageTk
                img = Image.fromarray(frame_rgb)
                imgtk = ImageTk.PhotoImage(image=img)
                
                # Mettre à jour le label
                self.camera_label.imgtk = imgtk
                self.camera_label.configure(image=imgtk)
                
                # Mettre à jour l'aperçu avec le frame adapté
                if self.preview_active:
                    self.update_preview(adapted_frame)
            
            # Planifier la prochaine mise à jour
            self.root.after(30, self.update_camera)
    
    def adapt_camera_frame(self, frame):
        """Adapte le frame de la caméra au format cible selon le mode choisi"""
        mode = self.adaptation_mode.get()
        
        if mode == "auto":
            # Mode automatique: utilise l'adaptateur intelligent
            return self.camera_adapter.adapt_frame_to_target(frame)
        
        elif mode == "crop":
            # Recadrage forcé
            h, w = frame.shape[:2]
            target_h = CameraAdapter.TARGET_HEIGHT
            target_w = CameraAdapter.TARGET_WIDTH
            
            # Calculer le meilleur facteur d'échelle
            scale = max(target_w / w, target_h / h)
            new_w = int(w * scale)
            new_h = int(h * scale)
            
            resized = cv2.resize(frame, (new_w, new_h))
            
            # Recadrer au centre
            start_x = (new_w - target_w) // 2
            start_y = (new_h - target_h) // 2
            cropped = resized[start_y:start_y+target_h, start_x:start_x+target_w]
            
            return cropped
        
        elif mode == "stretch":
            # Étirement pur
            return cv2.resize(frame, (CameraAdapter.TARGET_WIDTH, CameraAdapter.TARGET_HEIGHT))
        
        elif mode == "pad":
            # Ajout de lettres noires pour préserver le ratio
            h, w = frame.shape[:2]
            target_h = CameraAdapter.TARGET_HEIGHT
            target_w = CameraAdapter.TARGET_WIDTH
            
            # Calculer le facteur d'échelle pour rentrer dans le cadre
            scale = min(target_w / w, target_h / h)
            new_w = int(w * scale)
            new_h = int(h * scale)
            
            resized = cv2.resize(frame, (new_w, new_h))
            
            # Créer un canevas noir
            canvas = np.zeros((target_h, target_w, 3), dtype=np.uint8)
            
            # Centrer l'image redimensionnée
            start_x = (target_w - new_w) // 2
            start_y = (target_h - new_h) // 2
            canvas[start_y:start_y+new_h, start_x:start_x+new_w] = resized
            
            return canvas
        
        else:
            # Fallback
            return cv2.resize(frame, (CameraAdapter.TARGET_WIDTH, CameraAdapter.TARGET_HEIGHT))
    
    def update_preview(self, event=None, camera_frame=None):
        """Met à jour l'aperçu avec la composition"""
        if not self.preview_active:
            return
            
        if camera_frame is None and self.camera_running and self.camera:
            ret, frame = self.camera.read()
            if not ret:
                return
            camera_frame = self.adapt_camera_frame(frame)
        
        if camera_frame is not None:
            set_name = self.current_set.get()
            composed = self.create_composition(camera_frame, set_name)
            
            if composed is not None:
                # Redimensionner pour l'affichage
                display_height = 600
                aspect_ratio = composed.shape[1] / composed.shape[0]
                display_width = int(display_height * aspect_ratio)
                
                composed_resized = cv2.resize(composed, (display_width, display_height))
                
                # Convertir en ImageTk
                img = Image.fromarray(composed_resized)
                imgtk = ImageTk.PhotoImage(image=img)
                
                # Mettre à jour le canvas avec défilement
                self.preview_canvas.delete("all")
                self.preview_canvas.create_image(0, 0, image=imgtk, anchor=tk.NW)
                self.preview_canvas.config(scrollregion=(0, 0, display_width, display_height))
                self.preview_canvas.imgtk = imgtk
    
    def create_composition(self, camera_frame, set_name):
        """Crée la composition finale avec détourage avancé"""
        if set_name not in self.fonds or set_name not in self.pps:
            return None
        
        config = self.sets[set_name]
        fond = self.fonds[set_name].copy()
        pp = self.pps[set_name]
        
        # Récupérer les paramètres
        zone_w, zone_h, zone_x, zone_y = config.zone_visible
        zoom = self.zoom_factor.get()
        
        # Redimensionner la caméra (maintenant au format cible)
        new_h = int(zone_h * zoom)
        new_w = int(zone_w * zoom)
        camera_resized = cv2.resize(camera_frame, (new_w, new_h))
        
        # Détourage avancé du fond vert
        person_mask = self.create_advanced_mask(camera_resized)
        
        # Extraire la personne
        person = cv2.bitwise_and(camera_resized, camera_resized, mask=person_mask)
        
        # Calculer la position
        center_x = zone_x + (zone_w - new_w) // 2 + int(self.adjust_x.get())
        center_y = zone_y + (zone_h - new_h) // 2 + int(self.adjust_y.get())
        
        # Limites
        center_x = max(0, min(center_x, fond.shape[1] - new_w))
        center_y = max(0, min(center_y, fond.shape[0] - new_h))
        
        # Appliquer le matting avancé
        roi = fond[center_y:center_y+new_h, center_x:center_x+new_w]
        
        # Créer un masque avec transparence progressive
        person_mask_float = person_mask.astype(np.float32) / 255.0
        
        # Appliquer le flou si demandé
        if self.green_config.blur.get() > 1:
            blur_size = self.green_config.blur.get()
            if blur_size % 2 == 0:
                blur_size += 1
            person_mask_float = cv2.GaussianBlur(person_mask_float, (blur_size, blur_size), 0)
        
        # Étendre à 3 canaux
        person_mask_3c = np.stack([person_mask_float] * 3, axis=2)
        
        # Mélanger avec matting
        blended = roi * (1 - person_mask_3c) + person * person_mask_3c
        blended = blended.astype(np.uint8)
        
        fond[center_y:center_y+new_h, center_x:center_x+new_w] = blended
        
        # Superposer le premier plan
        if pp.shape[2] == 4:  # RGBA
            alpha = pp[:, :, 3] / 255.0
            # Appliquer la force du matting aux bords du premier plan
            alpha = alpha * (1 - self.green_config.matting_strength.get()) + \
                    alpha * self.green_config.matting_strength.get()
            
            for c in range(3):
                fond[:pp.shape[0], :pp.shape[1], c] = \
                    fond[:pp.shape[0], :pp.shape[1], c] * (1 - alpha) + \
                    pp[:, :, c] * alpha
        else:
            fond[:pp.shape[0], :pp.shape[1]] = pp
        
        return fond
    
    def create_advanced_mask(self, image):
        """Crée un masque avancé pour le détourage du fond vert"""
        # Convertir en HSV
        hsv = cv2.cvtColor(image, cv2.COLOR_RGB2HSV)
        
        # Définir les plages de vert
        lower_green = np.array([
            self.green_config.hue_min.get(),
            self.green_config.sat_min.get(),
            self.green_config.val_min.get()
        ])
        upper_green = np.array([
            self.green_config.hue_max.get(),
            255,  # saturation max
            255   # valeur max
        ])
        
        # Créer le masque initial
        mask = cv2.inRange(hsv, lower_green, upper_green)
        mask_inv = cv2.bitwise_not(mask)
        
        # Appliquer l'érosion (supprimer les pixels parasites)
        if self.green_config.erosion.get() > 0:
            kernel = np.ones((self.green_config.erosion.get(), 
                             self.green_config.erosion.get()), np.uint8)
            mask_inv = cv2.erode(mask_inv, kernel, iterations=1)
        
        # Appliquer la dilatation (remplir les trous)
        if self.green_config.dilation.get() > 0:
            kernel = np.ones((self.green_config.dilation.get(), 
                             self.green_config.dilation.get()), np.uint8)
            mask_inv = cv2.dilate(mask_inv, kernel, iterations=1)
        
        # Appliquer le seuil de transparence sur les contours
        if self.green_config.edge_threshold.get() < 1.0:
            # Créer une version floutée du masque pour les bords
            blur_size = max(3, self.green_config.blur.get())
            if blur_size % 2 == 0:
                blur_size += 1
            mask_float = mask_inv.astype(np.float32) / 255.0
            mask_blurred = cv2.GaussianBlur(mask_float, (blur_size, blur_size), 0)
            
            # Appliquer le seuil
            threshold = self.green_config.edge_threshold.get()
            mask_inv = (mask_blurred * 255).astype(np.uint8)
            mask_inv[mask_blurred < threshold] = 0
        
        return mask_inv
    
    def capture_photo(self):
        """Capture et enregistre la photo"""
        if not self.camera_running or not self.camera:
            messagebox.showerror("Erreur", "Caméra non disponible. Démarrez la caméra d'abord.")
            return
        
        ret, frame = self.camera.read()
        if not ret:
            messagebox.showerror("Erreur", "Impossible de capturer l'image")
            return
        
        # Adapter le frame au format cible
        adapted_frame = self.adapt_camera_frame(frame)
        
        set_name = self.current_set.get()
        composed = self.create_composition(adapted_frame, set_name)
        
        if composed is not None:
            # Générer un nom de fichier
            timestamp = time.strftime("%Y%m%d_%H%M%S")
            ext = self.file_format.get().lower()
            filename = f"salon_bd_{set_name.replace(' ', '')}_{timestamp}.{ext}"
            filepath = self.output_dir / filename
            
            # Sauvegarder
            if ext == 'png':
                composed_bgr = cv2.cvtColor(composed, cv2.COLOR_RGB2BGRA)
            else:
                composed_bgr = cv2.cvtColor(composed, cv2.COLOR_RGB2BGR)
            
            cv2.imwrite(str(filepath), composed_bgr)
            
            self.status_label.config(text=f"Statut: Photo sauvegardée: {filename}")
            messagebox.showinfo("Succès", f"Photo enregistrée :\n{filepath}")
    
    def __del__(self):
        """Nettoyage à la fermeture"""
        if hasattr(self, 'camera') and self.camera:
            self.camera_running = False
            self.camera.release()

def main():
    root = tk.Tk()
    app = SalonBDApp(root)
    
    # Gestion de la fermeture
    def on_closing():
        app.stop_camera()
        root.destroy()
    
    root.protocol("WM_DELETE_WINDOW", on_closing)
    root.mainloop()

if __name__ == "__main__":
    main()