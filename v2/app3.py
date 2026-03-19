import cv2
import numpy as np
import tkinter as tk
from tkinter import filedialog, messagebox, ttk
from PIL import Image, ImageTk, ImageFilter, ImageEnhance
import os
from pathlib import Path
import pandas as pd
from datetime import datetime
import piexif
import piexif.helper

class ScrollableFrame(ttk.Frame):
    """Une frame défilante personnalisée"""
    def __init__(self, container, *args, **kwargs):
        super().__init__(container, *args, **kwargs)
        
        # Créer un canvas pour le défilement
        self.canvas = tk.Canvas(self, borderwidth=0, highlightthickness=0)
        
        # Créer une scrollbar verticale
        self.scrollbar = ttk.Scrollbar(self, orient="vertical", command=self.canvas.yview)
        
        # Créer la frame qui contiendra le contenu
        self.scrollable_frame = ttk.Frame(self.canvas)
        
        # Configurer le canvas
        self.scrollable_frame.bind(
            "<Configure>",
            lambda e: self.canvas.configure(scrollregion=self.canvas.bbox("all"))
        )
        
        # Créer une fenêtre dans le canvas pour la frame
        self.canvas_window = self.canvas.create_window((0, 0), window=self.scrollable_frame, anchor="nw")
        
        # Configurer le canvas pour redimensionner la fenêtre
        self.canvas.bind('<Configure>', self._configure_canvas)
        
        # Packer le canvas et la scrollbar
        self.canvas.pack(side="left", fill="both", expand=True)
        self.scrollbar.pack(side="right", fill="y")
        
        # Configurer le canvas pour utiliser la scrollbar
        self.canvas.configure(yscrollcommand=self.scrollbar.set)
        
        # Lier la molette de la souris
        self.bind_mousewheel()
        
    def _configure_canvas(self, event):
        """Redimensionne la fenêtre du canvas quand le canvas est redimensionné"""
        self.canvas.itemconfig(self.canvas_window, width=event.width)
        
    def bind_mousewheel(self):
        """Lie la molette de la souris au défilement"""
        def _on_mousewheel(event):
            self.canvas.yview_scroll(int(-1*(event.delta/120)), "units")
        
        self.canvas.bind_all("<MouseWheel>", _on_mousewheel)
        
    def unbind_mousewheel(self):
        """Délie la molette de la souris"""
        self.canvas.unbind_all("<MouseWheel>")

class ChromaKeyApp:
    def __init__(self, root):
        self.root = root
        self.root.title("Studio Photo Fond Vert - Salon BD")
        self.root.geometry("1400x900")
        
        # Variables
        self.camera = None
        self.is_running = False
        self.current_frame = None
        self.captured_photo = None
        
        # Paramètres caméra
        self.camera_index = tk.IntVar(value=0)
        self.cameras_list = []
        
        # Paramètres personne
        self.person_name = tk.StringVar()
        self.email = tk.StringVar()
        
        # Position de la personne (offset dans la zone visible)
        self.person_x = tk.IntVar(value=0)
        self.person_y = tk.IntVar(value=0)
        
        # Paramètres chroma key avancés
        self.lower_green = np.array([35, 40, 40])
        self.upper_green = np.array([85, 255, 255])
        
        # Dossier de sauvegarde
        self.save_directory = Path(os.environ['USERPROFILE']) / "Pictures" / "salonBD"
        self.create_save_directory()
        
        # Charger les données des sets
        self.load_set_data()
        
        # Images des sets
        self.background_image = None
        self.foreground_image = None
        self.current_set_data = None
        
        # Interface utilisateur
        self.setup_ui()
        
        # Scanner les caméras au démarrage
        self.scan_cameras()
        
    def load_set_data(self):
        """Charge les données des sets depuis le fichier Excel"""
        try:
            # Chercher le fichier Excel dans différents emplacements
            possible_paths = [
                'data.xlsx',
                './data.xlsx',
                '../data.xlsx',
                str(Path(__file__).parent / 'data.xlsx') if '__file__' in dir() else 'data.xlsx'
            ]
            
            excel_path = None
            for path in possible_paths:
                if path and os.path.exists(path):
                    excel_path = path
                    break
            
            if excel_path:
                # Lire le fichier Excel en gérant les NaN
                df = pd.read_excel(excel_path, sheet_name='Feuil1', skiprows=3, header=None)
                
                # Remplacer les NaN par 0 pour les colonnes numériques
                df = df.fillna(0)
                
                self.sets_data = {}
                for _, row in df.iterrows():
                    if pd.notna(row.iloc[0]):  # Vérifier que le set existe
                        set_name = str(row.iloc[0]).lower().replace(' ', '')
                        self.sets_data[set_name] = {
                            'background': str(row.iloc[1]) if pd.notna(row.iloc[1]) else f"fond{set_name[-1]}.png",
                            'foreground': str(row.iloc[2]) if pd.notna(row.iloc[2]) else f"pp{set_name[-1]}.png",
                            'bg_width': int(float(row.iloc[3])) if pd.notna(row.iloc[3]) else 2000,
                            'bg_height': int(float(row.iloc[4])) if pd.notna(row.iloc[4]) else 2000,
                            'visible_width': int(float(row.iloc[5])) if pd.notna(row.iloc[5]) else 1280,
                            'visible_height': int(float(row.iloc[6])) if pd.notna(row.iloc[6]) else 720,
                            'visible_x': int(float(row.iloc[7])) if pd.notna(row.iloc[7]) else 0,
                            'visible_y': int(float(row.iloc[8])) if pd.notna(row.iloc[8]) else 0
                        }
                print(f"Sets chargés avec succès: {list(self.sets_data.keys())}")
            else:
                print("Fichier Excel non trouvé, utilisation des données par défaut")
                self.use_default_set_data()
                
        except Exception as e:
            print(f"Erreur chargement Excel: {e}")
            self.use_default_set_data()
    
    def use_default_set_data(self):
        """Utilise les données par défaut si le fichier Excel n'est pas disponible"""
        self.sets_data = {
            'set1': {'background': 'fond1.png', 'foreground': 'pp1.png', 
                    'bg_width': 2000, 'bg_height': 1688, 
                    'visible_width': 1061, 'visible_height': 597, 
                    'visible_x': -80, 'visible_y': 959},
            'set2': {'background': 'fond2.png', 'foreground': 'pp2.png',
                    'bg_width': 2000, 'bg_height': 1414,
                    'visible_width': 2286, 'visible_height': 1286, 
                    'visible_x': -137, 'visible_y': 68},
            'set3': {'background': 'fond3.png', 'foreground': 'pp3.png',
                    'bg_width': 2000, 'bg_height': 2632,
                    'visible_width': 1267, 'visible_height': 711, 
                    'visible_x': 942, 'visible_y': 1713},
            'set4': {'background': 'fond4.png', 'foreground': 'pp4.png',
                    'bg_width': 2000, 'bg_height': 2633,
                    'visible_width': 1890, 'visible_height': 1063, 
                    'visible_x': 74, 'visible_y': 1253}
        }
    
    def scan_cameras(self):
        """Scanne les caméras disponibles"""
        self.cameras_list = []
        for i in range(10):
            try:
                cap = cv2.VideoCapture(i, cv2.CAP_DSHOW)
                if cap.isOpened():
                    self.cameras_list.append(f"Caméra {i}")
                    cap.release()
            except:
                pass
        
        if self.cameras_list:
            self.camera_combo['values'] = self.cameras_list
            self.camera_index.set(0)
            self.status_bar.config(text=f"{len(self.cameras_list)} caméra(s) détectée(s)")
        else:
            self.camera_combo['values'] = ['Aucune caméra']
            self.status_bar.config(text="Aucune caméra détectée")
    
    def create_save_directory(self):
        """Crée le dossier de sauvegarde s'il n'existe pas"""
        try:
            self.save_directory.mkdir(parents=True, exist_ok=True)
        except Exception as e:
            print(f"Erreur lors de la création du dossier: {e}")
    
    def setup_ui(self):
        # Style
        style = ttk.Style()
        style.configure('Title.TLabel', font=('Arial', 16, 'bold'))
        style.configure('Heading.TLabel', font=('Arial', 12, 'bold'))
        
        # Frame principal
        main_frame = ttk.Frame(self.root)
        main_frame.pack(fill=tk.BOTH, expand=True, padx=10, pady=10)
        
        # Zone vidéo (à gauche)
        video_frame = ttk.Frame(main_frame)
        video_frame.pack(side=tk.LEFT, padx=5, fill=tk.BOTH, expand=True)
        
        self.video_label = ttk.Label(video_frame)
        self.video_label.pack(expand=True)
        
        # Informations set en cours
        self.set_info_label = ttk.Label(video_frame, text="", foreground="blue")
        self.set_info_label.pack(pady=5)
        
        # Frame défilante pour les contrôles (à droite)
        self.controls_container = ttk.Frame(main_frame, width=500)
        self.controls_container.pack(side=tk.RIGHT, fill=tk.Y, padx=10)
        self.controls_container.pack_propagate(False)
        
        # Créer la frame défilante
        self.scrollable_frame = ScrollableFrame(self.controls_container)
        self.scrollable_frame.pack(fill=tk.BOTH, expand=True)
        
        # Obtenir la frame intérieure pour y placer les contrôles
        controls_frame = self.scrollable_frame.scrollable_frame
        
        # Titre
        ttk.Label(controls_frame, text="📸 Studio Photo Salon BD", style='Title.TLabel').pack(pady=10)
        
        # Section Caméra
        self.create_camera_section(controls_frame)
        
        # Section Set
        self.create_set_section(controls_frame)
        
        # Section Informations personne
        self.create_person_info_section(controls_frame)
        
        # Section Position personne
        self.create_position_section(controls_frame)
        
        # Section Paramètres détourage
        self.create_chroma_section(controls_frame)
        
        # Section Actions
        self.create_actions_section(controls_frame)
        
        # Status bar (créée APRÈS les autres sections pour être disponible)
        self.status_bar = ttk.Label(self.root, text="Prêt", relief=tk.SUNKEN)
        self.status_bar.pack(side=tk.BOTTOM, fill=tk.X)
    
    def create_camera_section(self, parent):
        """Section contrôle caméra"""
        camera_frame = ttk.LabelFrame(parent, text="📷 Caméra", padding=10)
        camera_frame.pack(fill=tk.X, pady=5)
        
        # Sélection caméra
        select_frame = ttk.Frame(camera_frame)
        select_frame.pack(fill=tk.X, pady=5)
        
        ttk.Label(select_frame, text="Caméra:").pack(side=tk.LEFT)
        self.camera_combo = ttk.Combobox(select_frame, textvariable=self.camera_index, 
                                        values=self.cameras_list, width=15)
        self.camera_combo.pack(side=tk.LEFT, padx=5)
        
        ttk.Button(select_frame, text="🔄 Scanner", 
                  command=self.scan_cameras).pack(side=tk.LEFT)
        
        # Boutons contrôle
        btn_frame = ttk.Frame(camera_frame)
        btn_frame.pack(fill=tk.X)
        
        self.start_btn = ttk.Button(btn_frame, text="▶ Démarrer", 
                                   command=self.start_camera)
        self.start_btn.pack(side=tk.LEFT, padx=2, fill=tk.X, expand=True)
        
        self.stop_btn = ttk.Button(btn_frame, text="⏹ Arrêter", 
                                  command=self.stop_camera, state=tk.DISABLED)
        self.stop_btn.pack(side=tk.LEFT, padx=2, fill=tk.X, expand=True)
    
    def create_set_section(self, parent):
        """Section sélection du set"""
        set_frame = ttk.LabelFrame(parent, text="🎬 Set", padding=10)
        set_frame.pack(fill=tk.X, pady=5)
        
        # Sélection du set
        set_select_frame = ttk.Frame(set_frame)
        set_select_frame.pack(fill=tk.X)
        
        ttk.Label(set_select_frame, text="Set:").pack(side=tk.LEFT)
        self.set_combo = ttk.Combobox(set_select_frame, 
                                      values=['set 1', 'set 2', 'set 3', 'set 4'],
                                      state='readonly', width=10)
        self.set_combo.pack(side=tk.LEFT, padx=5)
        self.set_combo.set('set 1')
        self.set_combo.bind('<<ComboboxSelected>>', self.on_set_change)
        
        ttk.Button(set_select_frame, text="Charger", 
                  command=self.load_current_set).pack(side=tk.LEFT)
        
        # Labels d'information
        self.bg_label = ttk.Label(set_frame, text="Fond: Non chargé")
        self.bg_label.pack(anchor=tk.W, pady=2)
        
        self.fg_label = ttk.Label(set_frame, text="Premier plan: Non chargé")
        self.fg_label.pack(anchor=tk.W, pady=2)
        
        self.zone_label = ttk.Label(set_frame, text="Zone visible: -")
        self.zone_label.pack(anchor=tk.W, pady=2)
        
        # Charger le premier set
        self.load_current_set()
    
    def create_person_info_section(self, parent):
        """Section informations de la personne"""
        info_frame = ttk.LabelFrame(parent, text="👤 Informations personne", padding=10)
        info_frame.pack(fill=tk.X, pady=5)
        
        ttk.Label(info_frame, text="Nom:").pack(anchor=tk.W)
        name_entry = ttk.Entry(info_frame, textvariable=self.person_name, width=40)
        name_entry.pack(fill=tk.X, pady=2)
        
        ttk.Label(info_frame, text="Email:").pack(anchor=tk.W)
        email_entry = ttk.Entry(info_frame, textvariable=self.email, width=40)
        email_entry.pack(fill=tk.X, pady=2)
    
    def create_position_section(self, parent):
        """Section ajustement position de la personne"""
        pos_frame = ttk.LabelFrame(parent, text="🎯 Position dans le décor", padding=10)
        pos_frame.pack(fill=tk.X, pady=5)
        
        # Position X
        x_frame = ttk.Frame(pos_frame)
        x_frame.pack(fill=tk.X, pady=2)
        ttk.Label(x_frame, text="Position X:").pack(side=tk.LEFT)
        self.x_scale = ttk.Scale(x_frame, from_=-500, to=500, 
                                 variable=self.person_x, orient=tk.HORIZONTAL,
                                 command=self.update_position_display)
        self.x_scale.pack(side=tk.LEFT, fill=tk.X, expand=True, padx=5)
        self.x_label = ttk.Label(x_frame, text="0", width=5)
        self.x_label.pack(side=tk.RIGHT)
        
        # Position Y
        y_frame = ttk.Frame(pos_frame)
        y_frame.pack(fill=tk.X, pady=2)
        ttk.Label(y_frame, text="Position Y:").pack(side=tk.LEFT)
        self.y_scale = ttk.Scale(y_frame, from_=-500, to=500, 
                                 variable=self.person_y, orient=tk.HORIZONTAL,
                                 command=self.update_position_display)
        self.y_scale.pack(side=tk.LEFT, fill=tk.X, expand=True, padx=5)
        self.y_label = ttk.Label(y_frame, text="0", width=5)
        self.y_label.pack(side=tk.RIGHT)
        
        # Bouton reset
        ttk.Button(pos_frame, text="↺ Réinitialiser", 
                  command=self.reset_position).pack(pady=5)
    
    def create_chroma_section(self, parent):
        """Section paramètres chroma key"""
        chroma_frame = ttk.LabelFrame(parent, text="🎨 Détourage précis", padding=10)
        chroma_frame.pack(fill=tk.X, pady=5)
        
        # Plage de couleur verte
        ttk.Label(chroma_frame, text="Plage de couleur verte:").pack()
        
        # Teinte Min
        ttk.Label(chroma_frame, text="Teinte Min (35-85):").pack()
        self.hue_min = tk.Scale(chroma_frame, from_=0, to=179, orient=tk.HORIZONTAL,
                                command=self.update_params)
        self.hue_min.set(35)
        self.hue_min.pack(fill=tk.X)
        
        # Teinte Max
        ttk.Label(chroma_frame, text="Teinte Max:").pack()
        self.hue_max = tk.Scale(chroma_frame, from_=0, to=179, orient=tk.HORIZONTAL,
                                command=self.update_params)
        self.hue_max.set(85)
        self.hue_max.pack(fill=tk.X)
        
        # Saturation Min
        ttk.Label(chroma_frame, text="Saturation Min (40):").pack()
        self.sat_min = tk.Scale(chroma_frame, from_=0, to=255, orient=tk.HORIZONTAL,
                                command=self.update_params)
        self.sat_min.set(40)
        self.sat_min.pack(fill=tk.X)
        
        # Valeur Min
        ttk.Label(chroma_frame, text="Luminosité Min (40):").pack()
        self.val_min = tk.Scale(chroma_frame, from_=0, to=255, orient=tk.HORIZONTAL,
                                command=self.update_params)
        self.val_min.set(40)
        self.val_min.pack(fill=tk.X)
        
        # Paramètres morphologiques
        ttk.Label(chroma_frame, text="Flou (adoucit les bords):").pack()
        self.blur_var = tk.IntVar(value=3)
        blur_frame = ttk.Frame(chroma_frame)
        blur_frame.pack(fill=tk.X)
        ttk.Scale(blur_frame, from_=1, to=15, orient=tk.HORIZONTAL,
                 variable=self.blur_var, command=self.update_params).pack(side=tk.LEFT, fill=tk.X, expand=True)
        ttk.Label(blur_frame, textvariable=self.blur_var, width=3).pack(side=tk.RIGHT)
        
        ttk.Label(chroma_frame, text="Érosion (supprime parasites):").pack()
        self.erode_var = tk.IntVar(value=1)
        erode_frame = ttk.Frame(chroma_frame)
        erode_frame.pack(fill=tk.X)
        ttk.Scale(erode_frame, from_=0, to=5, orient=tk.HORIZONTAL,
                 variable=self.erode_var, command=self.update_params).pack(side=tk.LEFT, fill=tk.X, expand=True)
        ttk.Label(erode_frame, textvariable=self.erode_var, width=3).pack(side=tk.RIGHT)
        
        ttk.Label(chroma_frame, text="Dilatation (remplit les trous):").pack()
        self.dilate_var = tk.IntVar(value=1)
        dilate_frame = ttk.Frame(chroma_frame)
        dilate_frame.pack(fill=tk.X)
        ttk.Scale(dilate_frame, from_=0, to=5, orient=tk.HORIZONTAL,
                 variable=self.dilate_var, command=self.update_params).pack(side=tk.LEFT, fill=tk.X, expand=True)
        ttk.Label(dilate_frame, textvariable=self.dilate_var, width=3).pack(side=tk.RIGHT)
        
        # Bouton reset
        ttk.Button(chroma_frame, text="↺ Reset détourage", 
                  command=self.reset_chroma_params).pack(pady=10)
    
    def create_actions_section(self, parent):
        """Section actions"""
        actions_frame = ttk.LabelFrame(parent, text="📸 Actions", padding=10)
        actions_frame.pack(fill=tk.X, pady=5)
        
        # Bouton prise de vue
        self.capture_btn = ttk.Button(actions_frame, text="📷 PRENDRE LA PHOTO", 
                                     command=self.take_photo, state=tk.DISABLED)
        self.capture_btn.pack(fill=tk.X, pady=5)
        
        # Aperçu rapide
        self.preview_label = ttk.Label(actions_frame, text="")
        self.preview_label.pack(pady=5)
        
        # Info dossier
        folder_info = f"Dossier de sauvegarde:\n{self.save_directory}"
        ttk.Label(actions_frame, text=folder_info, foreground="blue").pack(pady=5)
    
    def update_position_display(self, event=None):
        """Met à jour l'affichage des positions"""
        self.x_label.config(text=str(self.person_x.get()))
        self.y_label.config(text=str(self.person_y.get()))
    
    def reset_position(self):
        """Réinitialise la position"""
        self.person_x.set(0)
        self.person_y.set(0)
    
    def reset_chroma_params(self):
        """Réinitialise les paramètres de détourage"""
        self.hue_min.set(35)
        self.hue_max.set(85)
        self.sat_min.set(40)
        self.val_min.set(40)
        self.blur_var.set(3)
        self.erode_var.set(1)
        self.dilate_var.set(1)
        self.update_params()
    
    def update_params(self, event=None):
        """Met à jour les paramètres de détourage"""
        self.lower_green = np.array([self.hue_min.get(), self.sat_min.get(), self.val_min.get()])
        self.upper_green = np.array([self.hue_max.get(), 255, 255])
    
    def on_set_change(self, event=None):
        """Quand le set change, charger les nouvelles images"""
        self.load_current_set()
    
    def load_current_set(self):
        """Charge les images du set sélectionné"""
        set_key = self.set_combo.get().lower().replace(' ', '')
        
        if set_key in self.sets_data:
            self.current_set_data = self.sets_data[set_key]
            
            # Charger le fond
            bg_path = self.current_set_data['background']
            if os.path.exists(bg_path):
                self.background_image = cv2.imread(bg_path, cv2.IMREAD_UNCHANGED)
                self.bg_label.config(text=f"✓ Fond: {os.path.basename(bg_path)}", 
                                    foreground="green")
            else:
                self.background_image = None
                self.bg_label.config(text=f"✗ Fond non trouvé: {bg_path}", 
                                    foreground="red")
            
            # Charger le premier plan
            fg_path = self.current_set_data['foreground']
            if os.path.exists(fg_path):
                self.foreground_image = cv2.imread(fg_path, cv2.IMREAD_UNCHANGED)
                self.fg_label.config(text=f"✓ Premier plan: {os.path.basename(fg_path)}", 
                                    foreground="green")
            else:
                self.foreground_image = None
                self.fg_label.config(text=f"✗ Premier plan non trouvé: {fg_path}", 
                                    foreground="red")
            
            # Afficher les infos de la zone visible
            zone_info = (f"Zone visible: {self.current_set_data['visible_width']}x"
                        f"{self.current_set_data['visible_height']}px à position "
                        f"({self.current_set_data['visible_x']}, {self.current_set_data['visible_y']})")
            self.zone_label.config(text=zone_info)
            
            if hasattr(self, 'status_bar'):
                self.status_bar.config(text=f"Set {set_key} chargé")
        else:
            messagebox.showerror("Erreur", f"Set {set_key} non trouvé")
    
    def start_camera(self):
        """Démarre la caméra"""
        if not self.is_running:
            try:
                camera_text = self.camera_combo.get()
                if camera_text and camera_text != 'Aucune caméra':
                    camera_idx = int(camera_text.split()[-1])
                    self.camera = cv2.VideoCapture(camera_idx, cv2.CAP_DSHOW)
                    
                    # Configurer pour Logitech C270 HD (1280x720)
                    self.camera.set(cv2.CAP_PROP_FRAME_WIDTH, 1280)
                    self.camera.set(cv2.CAP_PROP_FRAME_HEIGHT, 720)
                    self.camera.set(cv2.CAP_PROP_FPS, 30)
                    self.camera.set(cv2.CAP_PROP_BUFFERSIZE, 1)
                    
                    if self.camera.isOpened():
                        self.is_running = True
                        self.update_frame()
                        self.start_btn.config(state=tk.DISABLED)
                        self.stop_btn.config(state=tk.NORMAL)
                        self.capture_btn.config(state=tk.NORMAL)
                        self.status_bar.config(text="Caméra active - Logitech C270 HD")
                    else:
                        messagebox.showerror("Erreur", "Impossible d'ouvrir la caméra")
                else:
                    messagebox.showerror("Erreur", "Aucune caméra sélectionnée")
            except Exception as e:
                messagebox.showerror("Erreur", f"Erreur caméra: {e}")
    
    def stop_camera(self):
        """Arrête la caméra"""
        self.is_running = False
        if self.camera:
            self.camera.release()
        self.video_label.config(image='')
        self.start_btn.config(state=tk.NORMAL)
        self.stop_btn.config(state=tk.DISABLED)
        self.capture_btn.config(state=tk.DISABLED)
        self.status_bar.config(text="Caméra arrêtée")
    
    def apply_chroma_key(self, frame):
        """Applique le chroma key avec le fond du set"""
        if self.background_image is None:
            return frame
        
        h, w = frame.shape[:2]
        
        # Redimensionner le fond à la taille de la zone visible du set
        if self.current_set_data:
            visible_w = self.current_set_data['visible_width']
            visible_h = self.current_set_data['visible_height']
            bg_resized = cv2.resize(self.background_image, (visible_w, visible_h))
        else:
            bg_resized = cv2.resize(self.background_image, (w, h))
        
        # Convertir en HSV pour détection du vert
        hsv = cv2.cvtColor(frame, cv2.COLOR_BGR2HSV)
        
        # Créer le masque
        mask = cv2.inRange(hsv, self.lower_green, self.upper_green)
        
        # Nettoyer le masque
        if self.blur_var.get() > 1:
            blur_size = self.blur_var.get()
            if blur_size % 2 == 0:
                blur_size += 1
            mask = cv2.GaussianBlur(mask, (blur_size, blur_size), 0)
        
        kernel = np.ones((3, 3), np.uint8)
        if self.erode_var.get() > 0:
            mask = cv2.erode(mask, kernel, iterations=self.erode_var.get())
        if self.dilate_var.get() > 0:
            mask = cv2.dilate(mask, kernel, iterations=self.dilate_var.get())
        
        # Inverser le masque pour garder la personne
        mask_inv = cv2.bitwise_not(mask)
        
        # Normaliser le masque pour le mélange
        mask_float = mask.astype(np.float32) / 255.0
        mask_inv_float = mask_inv.astype(np.float32) / 255.0
        
        # Créer le résultat avec le fond redimensionné
        result = np.zeros((h, w, 3), dtype=np.uint8)
        
        # La zone visible du fond
        if self.current_set_data:
            # Calculer la position de la zone visible avec l'offset de la personne
            visible_x = self.current_set_data['visible_x'] + self.person_x.get()
            visible_y = self.current_set_data['visible_y'] + self.person_y.get()
            visible_w = self.current_set_data['visible_width']
            visible_h = self.current_set_data['visible_height']
            
            # Créer une image vide de la taille de la frame
            full_bg = np.zeros((h, w, 3), dtype=np.uint8)
            
            # Positionner la zone visible
            x_start = max(0, visible_x)
            y_start = max(0, visible_y)
            x_end = min(w, visible_x + visible_w)
            y_end = min(h, visible_y + visible_h)
            
            # Calculer les parties correspondantes de l'image de fond
            bg_x_start = max(0, -visible_x)
            bg_y_start = max(0, -visible_y)
            bg_x_end = bg_x_start + (x_end - x_start)
            bg_y_end = bg_y_start + (y_end - y_start)
            
            if bg_x_end > 0 and bg_y_end > 0 and bg_x_start < bg_resized.shape[1] and bg_y_start < bg_resized.shape[0]:
                bg_x_end = min(bg_x_end, bg_resized.shape[1])
                bg_y_end = min(bg_y_end, bg_resized.shape[0])
                full_bg[y_start:y_end, x_start:x_end] = bg_resized[bg_y_start:bg_y_end, bg_x_start:bg_x_end]
            
            # Composition
            for c in range(3):
                result[:, :, c] = (frame[:, :, c] * mask_inv_float + 
                                  full_bg[:, :, c] * mask_float)
        else:
            # Composition simple
            for c in range(3):
                result[:, :, c] = (frame[:, :, c] * mask_inv_float + 
                                  bg_resized[:, :, c] * mask_float)
        
        # Ajouter le premier plan (PNG avec transparence)
        if self.foreground_image is not None and self.foreground_image.shape[2] == 4:
            fg_h, fg_w = self.foreground_image.shape[:2]
            
            # Redimensionner le premier plan à la taille de la frame
            fg_resized = cv2.resize(self.foreground_image, (w, h))
            
            # Extraire les canaux
            fg_rgb = fg_resized[:, :, :3]
            fg_alpha = fg_resized[:, :, 3] / 255.0
            
            # Mélanger avec le résultat
            result_float = result.astype(np.float32)
            fg_rgb_float = fg_rgb.astype(np.float32)
            
            for c in range(3):
                result_float[:, :, c] = (fg_rgb_float[:, :, c] * fg_alpha + 
                                        result_float[:, :, c] * (1 - fg_alpha))
            
            result = np.clip(result_float, 0, 255).astype(np.uint8)
        
        return result
    
    def update_frame(self):
        """Met à jour l'affichage vidéo"""
        if self.is_running:
            ret, frame = self.camera.read()
            if ret:
                # Appliquer le chroma key
                processed = self.apply_chroma_key(frame)
                self.current_frame = processed.copy()
                
                # Convertir pour affichage
                rgb = cv2.cvtColor(processed, cv2.COLOR_BGR2RGB)
                pil_image = Image.fromarray(rgb)
                
                # Redimensionner pour l'affichage
                pil_image.thumbnail((800, 600), Image.Resampling.LANCZOS)
                
                # Convertir pour tkinter
                tk_image = ImageTk.PhotoImage(pil_image)
                self.video_label.config(image=tk_image)
                self.video_label.image = tk_image
                
                # Mettre à jour les infos du set
                if self.current_set_data:
                    info = (f"Set: {self.set_combo.get()} | "
                           f"Position: X={self.person_x.get()}, Y={self.person_y.get()}")
                    self.set_info_label.config(text=info)
            
            self.root.after(30, self.update_frame)
    
    def take_photo(self):
        """Prend une photo et l'enregistre"""
        if not self.is_running:
            messagebox.showwarning("Attention", "Veuillez démarrer la caméra")
            return
        
        if not self.person_name.get().strip():
            messagebox.showwarning("Attention", "Veuillez entrer le nom de la personne")
            return
        
        if not self.email.get().strip():
            messagebox.showwarning("Attention", "Veuillez entrer l'adresse email")
            return
        
        # Capturer en haute résolution
        ret, high_res = self.camera.read()
        if ret:
            self.captured_photo = self.apply_chroma_key(high_res)
            
            # Mettre à jour l'aperçu
            rgb_preview = cv2.cvtColor(self.captured_photo, cv2.COLOR_BGR2RGB)
            pil_preview = Image.fromarray(rgb_preview)
            pil_preview.thumbnail((150, 150))
            tk_preview = ImageTk.PhotoImage(pil_preview)
            self.preview_label.config(image=tk_preview)
            self.preview_label.image = tk_preview
            
            # Sauvegarder automatiquement
            self.save_photo_auto()
    
    def save_photo_auto(self):
        """Sauvegarde automatique avec nom et métadonnées"""
        if self.captured_photo is not None:
            try:
                # Générer le nom de fichier
                timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
                name_clean = self.person_name.get().replace(' ', '_')
                filename = f"{name_clean}_{timestamp}.jpg"
                filepath = self.save_directory / filename
                
                # Sauvegarder avec métadonnées
                self.save_image_with_metadata(self.captured_photo, filepath)
                
                self.status_bar.config(text=f"✓ Photo sauvegardée: {filename}")
                messagebox.showinfo("Succès", f"Photo enregistrée:\n{filepath}")
                
            except Exception as e:
                messagebox.showerror("Erreur", f"Erreur sauvegarde: {e}")
    
    def save_image_with_metadata(self, image, filepath):
        """Sauvegarde l'image avec les métadonnées EXIF"""
        # Convertir BGR en RGB pour PIL
        rgb_image = cv2.cvtColor(image, cv2.COLOR_BGR2RGB)
        pil_image = Image.fromarray(rgb_image)
        
        # Créer les métadonnées EXIF
        exif_dict = {"0th": {}, "Exif": {}, "GPS": {}, "1st": {}, "thumbnail": None}
        
        # Ajouter l'email comme commentaire
        user_comment = piexif.helper.UserComment.dump(
            f"Email: {self.email.get()}", 
            encoding="unicode"
        )
        exif_dict["Exif"][piexif.ExifIFD.UserComment] = user_comment
        
        # Ajouter d'autres informations
        exif_dict["0th"][piexif.ImageIFD.ImageDescription] = (
            f"Photo de {self.person_name.get()} - Set: {self.set_combo.get()} - "
            f"Position: X={self.person_x.get()}, Y={self.person_y.get()}"
        )
        exif_dict["0th"][piexif.ImageIFD.DateTime] = datetime.now().strftime("%Y:%m:%d %H:%M:%S")
        exif_dict["0th"][piexif.ImageIFD.Software] = "Studio Photo Salon BD"
        exif_dict["0th"][piexif.ImageIFD.Artist] = self.person_name.get()
        
        # Convertir en bytes
        exif_bytes = piexif.dump(exif_dict)
        
        # Sauvegarder
        pil_image.save(filepath, "JPEG", exif=exif_bytes, quality=95)

if __name__ == "__main__":
    root = tk.Tk()
    app = ChromaKeyApp(root)
    root.mainloop()