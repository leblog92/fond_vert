import cv2
import numpy as np
import tkinter as tk
from tkinter import filedialog, messagebox, ttk
from PIL import Image, ImageTk, ImageFilter, ImageEnhance
import os
from pathlib import Path

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
        self.root.title("Application Chroma Key - Détourage Haute Précision")
        self.root.geometry("1400x800")
        
        # Variables
        self.camera = None
        self.is_running = False
        self.current_frame = None
        self.background_image = None
        self.background_path = None
        self.overlay_image = None
        self.overlay_path = None
        self.captured_photo = None
        
        # Dossier de sauvegarde par défaut
        self.save_directory = Path(os.environ['USERPROFILE']) / "Pictures" / "salon BD"
        self.create_save_directory()
        
        # Paramètres chroma key avancés
        self.lower_green = np.array([35, 40, 40])
        self.upper_green = np.array([85, 255, 255])
        
        # Paramètres d'overlay
        self.overlay_opacity = 0.8
        self.overlay_position = (0, 0)
        
        # Interface utilisateur
        self.setup_ui()
        
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
        
        # Frame défilante pour les contrôles (à droite)
        self.controls_container = ttk.Frame(main_frame, width=450)
        self.controls_container.pack(side=tk.RIGHT, fill=tk.Y, padx=10)
        self.controls_container.pack_propagate(False)
        
        # Créer la frame défilante
        self.scrollable_frame = ScrollableFrame(self.controls_container)
        self.scrollable_frame.pack(fill=tk.BOTH, expand=True)
        
        # Obtenir la frame intérieure pour y placer les contrôles
        controls_frame = self.scrollable_frame.scrollable_frame
        
        # Titre
        ttk.Label(controls_frame, text="🎬 Contrôles Chroma Key Pro", style='Title.TLabel').pack(pady=10)
        
        # Section Caméra
        self.create_camera_section(controls_frame)
        
        # Section Image de fond
        self.create_background_section(controls_frame)
        
        # Section Image de premier plan (Overlay)
        self.create_overlay_section(controls_frame)
        
        # Section Ajustements avancés
        self.create_advanced_adjustments_section(controls_frame)
        
        # Section Actions
        self.create_actions_section(controls_frame)
        
        # Status bar
        self.status_bar = ttk.Label(self.root, text="Prêt", relief=tk.SUNKEN)
        self.status_bar.pack(side=tk.BOTTOM, fill=tk.X)
        
    def create_camera_section(self, parent):
        """Section contrôle caméra"""
        camera_frame = ttk.LabelFrame(parent, text="📷 Caméra", padding=10)
        camera_frame.pack(fill=tk.X, pady=5)
        
        btn_frame = ttk.Frame(camera_frame)
        btn_frame.pack(fill=tk.X)
        
        self.start_btn = ttk.Button(btn_frame, text="Démarrer Caméra", 
                                   command=self.start_camera)
        self.start_btn.pack(side=tk.LEFT, padx=2, fill=tk.X, expand=True)
        
        self.stop_btn = ttk.Button(btn_frame, text="Arrêter", 
                                  command=self.stop_camera, state=tk.DISABLED)
        self.stop_btn.pack(side=tk.LEFT, padx=2, fill=tk.X, expand=True)
        
    def create_background_section(self, parent):
        """Section chargement de l'image de fond"""
        bg_frame = ttk.LabelFrame(parent, text="🖼️ Image de fond", padding=10)
        bg_frame.pack(fill=tk.X, pady=5)
        
        self.bg_btn = ttk.Button(bg_frame, text="Charger Image de fond", 
                                command=self.load_background)
        self.bg_btn.pack(fill=tk.X, pady=2)
        
        self.bg_label = ttk.Label(bg_frame, text="Aucune image de fond chargée", 
                                 foreground="gray")
        self.bg_label.pack(pady=2)
        
    def create_overlay_section(self, parent):
        """Section chargement de l'image de premier plan (overlay)"""
        overlay_frame = ttk.LabelFrame(parent, text="🖼️ Image de premier plan (Overlay PNG)", padding=10)
        overlay_frame.pack(fill=tk.X, pady=5)
        
        self.overlay_btn = ttk.Button(overlay_frame, text="Charger Image PNG (transparente)", 
                                     command=self.load_overlay)
        self.overlay_btn.pack(fill=tk.X, pady=2)
        
        self.overlay_label = ttk.Label(overlay_frame, text="Aucune image de premier plan", 
                                      foreground="gray")
        self.overlay_label.pack(pady=2)
        
        # Contrôles de position de l'overlay
        position_frame = ttk.Frame(overlay_frame)
        position_frame.pack(fill=tk.X, pady=5)
        
        ttk.Label(position_frame, text="Position X:").pack(side=tk.LEFT)
        self.overlay_x = tk.Scale(position_frame, from_=0, to=1000, orient=tk.HORIZONTAL, 
                                  command=self.update_overlay_position)
        self.overlay_x.pack(side=tk.LEFT, fill=tk.X, expand=True)
        
        position_frame2 = ttk.Frame(overlay_frame)
        position_frame2.pack(fill=tk.X, pady=5)
        
        ttk.Label(position_frame2, text="Position Y:").pack(side=tk.LEFT)
        self.overlay_y = tk.Scale(position_frame2, from_=0, to=1000, orient=tk.HORIZONTAL, 
                                  command=self.update_overlay_position)
        self.overlay_y.pack(side=tk.LEFT, fill=tk.X, expand=True)
        
        # Opacité de l'overlay
        ttk.Label(overlay_frame, text="Opacité:").pack()
        self.opacity_scale = tk.Scale(overlay_frame, from_=0, to=100, orient=tk.HORIZONTAL,
                                      command=self.update_overlay_opacity)
        self.opacity_scale.set(80)
        self.opacity_scale.pack(fill=tk.X)
        
        # Bouton pour centrer l'overlay
        ttk.Button(overlay_frame, text="Centrer l'image", 
                  command=self.center_overlay).pack(pady=5)
        
        # Bouton pour supprimer l'overlay
        ttk.Button(overlay_frame, text="Supprimer l'overlay", 
                  command=self.remove_overlay).pack(pady=2)
        
    def update_overlay_position(self, event=None):
        """Met à jour la position de l'overlay"""
        if self.overlay_image is not None:
            self.overlay_position = (self.overlay_x.get(), self.overlay_y.get())
            
    def update_overlay_opacity(self, event=None):
        """Met à jour l'opacité de l'overlay"""
        self.overlay_opacity = self.opacity_scale.get() / 100.0
        
    def center_overlay(self):
        """Centre l'overlay sur l'image"""
        if self.current_frame is not None and self.overlay_image is not None:
            h, w = self.current_frame.shape[:2]
            overlay_h, overlay_w = self.overlay_image.shape[:2]
            
            center_x = (w - overlay_w) // 2
            center_y = (h - overlay_h) // 2
            
            self.overlay_x.set(max(0, center_x))
            self.overlay_y.set(max(0, center_y))
            self.overlay_position = (center_x, center_y)
            
    def remove_overlay(self):
        """Supprime l'image de premier plan"""
        self.overlay_image = None
        self.overlay_path = None
        self.overlay_label.config(text="Aucune image de premier plan", foreground="gray")
        self.status_bar.config(text="Overlay supprimé")
        
    def create_advanced_adjustments_section(self, parent):
        """Section ajustements avancés pour détourage précis"""
        adjust_frame = ttk.LabelFrame(parent, text="🎨 Ajustements Détourage Avancé", padding=10)
        adjust_frame.pack(fill=tk.X, pady=5)
        
        # Plage de couleur verte
        ttk.Label(adjust_frame, text="--- Plage de Couleur Verte ---", 
                 font=('Arial', 9, 'bold')).pack(pady=5)
        
        # Teinte Min
        ttk.Label(adjust_frame, text="Teinte (Hue) Min:").pack()
        self.hue_min = tk.Scale(adjust_frame, from_=0, to=179, orient=tk.HORIZONTAL, 
                               length=300, command=self.update_params)
        self.hue_min.set(35)
        self.hue_min.pack()
        
        # Teinte Max
        ttk.Label(adjust_frame, text="Teinte Max:").pack()
        self.hue_max = tk.Scale(adjust_frame, from_=0, to=179, orient=tk.HORIZONTAL, 
                               length=300, command=self.update_params)
        self.hue_max.set(85)
        self.hue_max.pack()
        
        # Saturation Min
        ttk.Label(adjust_frame, text="Saturation Min:").pack()
        self.sat_min = tk.Scale(adjust_frame, from_=0, to=255, orient=tk.HORIZONTAL, 
                               length=300, command=self.update_params)
        self.sat_min.set(40)
        self.sat_min.pack()
        
        # Valeur Min
        ttk.Label(adjust_frame, text="Valeur (Luminosité) Min:").pack()
        self.val_min = tk.Scale(adjust_frame, from_=0, to=255, orient=tk.HORIZONTAL, 
                               length=300, command=self.update_params)
        self.val_min.set(40)
        self.val_min.pack()
        
        ttk.Separator(adjust_frame, orient='horizontal').pack(fill=tk.X, pady=10)
        
        # Paramètres de détourage fin
        ttk.Label(adjust_frame, text="--- Paramètres de Détourage Fin ---", 
                 font=('Arial', 9, 'bold')).pack(pady=5)
        
        # Érosion
        ttk.Label(adjust_frame, text="Érosion (supprime les pixels parasites):").pack()
        self.erode_var = tk.IntVar(value=1)
        erode_frame = ttk.Frame(adjust_frame)
        erode_frame.pack(fill=tk.X)
        ttk.Scale(erode_frame, from_=0, to=5, orient=tk.HORIZONTAL, 
                 variable=self.erode_var, command=self.update_params).pack(side=tk.LEFT, fill=tk.X, expand=True)
        ttk.Label(erode_frame, textvariable=self.erode_var, width=3).pack(side=tk.RIGHT)
        
        # Dilatation
        ttk.Label(adjust_frame, text="Dilatation (remplit les trous):").pack()
        self.dilate_var = tk.IntVar(value=1)
        dilate_frame = ttk.Frame(adjust_frame)
        dilate_frame.pack(fill=tk.X)
        ttk.Scale(dilate_frame, from_=0, to=5, orient=tk.HORIZONTAL, 
                 variable=self.dilate_var, command=self.update_params).pack(side=tk.LEFT, fill=tk.X, expand=True)
        ttk.Label(dilate_frame, textvariable=self.dilate_var, width=3).pack(side=tk.RIGHT)
        
        # Flou gaussien
        ttk.Label(adjust_frame, text="Flou des bords (adoucit le contour):").pack()
        self.blur_var = tk.IntVar(value=3)
        blur_frame = ttk.Frame(adjust_frame)
        blur_frame.pack(fill=tk.X)
        ttk.Scale(blur_frame, from_=1, to=15, orient=tk.HORIZONTAL, 
                 variable=self.blur_var, command=self.update_params).pack(side=tk.LEFT, fill=tk.X, expand=True)
        ttk.Label(blur_frame, textvariable=self.blur_var, width=3).pack(side=tk.RIGHT)
        
        ttk.Separator(adjust_frame, orient='horizontal').pack(fill=tk.X, pady=10)
        
        # Paramètres de matting
        ttk.Label(adjust_frame, text="--- Gestion des Contours ---", 
                 font=('Arial', 9, 'bold')).pack(pady=5)
        
        # Seuil de transparence
        ttk.Label(adjust_frame, text="Seuil de transparence des contours:").pack()
        self.edge_threshold_var = tk.IntVar(value=128)
        edge_frame = ttk.Frame(adjust_frame)
        edge_frame.pack(fill=tk.X)
        ttk.Scale(edge_frame, from_=0, to=255, orient=tk.HORIZONTAL, 
                 variable=self.edge_threshold_var, command=self.update_params).pack(side=tk.LEFT, fill=tk.X, expand=True)
        ttk.Label(edge_frame, textvariable=self.edge_threshold_var, width=3).pack(side=tk.RIGHT)
        
        # Force du matting
        ttk.Label(adjust_frame, text="Force du matting (transitions douces):").pack()
        self.matting_strength_var = tk.IntVar(value=50)
        matting_frame = ttk.Frame(adjust_frame)
        matting_frame.pack(fill=tk.X)
        ttk.Scale(matting_frame, from_=0, to=100, orient=tk.HORIZONTAL, 
                 variable=self.matting_strength_var, command=self.update_params).pack(side=tk.LEFT, fill=tk.X, expand=True)
        ttk.Label(matting_frame, textvariable=self.matting_strength_var, width=3).pack(side=tk.RIGHT)
        
        ttk.Separator(adjust_frame, orient='horizontal').pack(fill=tk.X, pady=10)
        
        # Options d'affichage
        ttk.Label(adjust_frame, text="--- Options d'Affichage ---", 
                 font=('Arial', 9, 'bold')).pack(pady=5)
        
        self.show_mask_var = tk.BooleanVar(value=False)
        ttk.Checkbutton(adjust_frame, text="Afficher le masque", 
                       variable=self.show_mask_var).pack()
        
        self.show_edges_var = tk.BooleanVar(value=False)
        ttk.Checkbutton(adjust_frame, text="Afficher les contours détectés", 
                       variable=self.show_edges_var).pack()
        
        # Bouton de réinitialisation
        ttk.Button(adjust_frame, text="↺ Réinitialiser les paramètres", 
                  command=self.reset_parameters).pack(pady=10)
        
        # Espace en bas pour un meilleur défilement
        ttk.Label(adjust_frame, text="").pack(pady=20)
        
    def create_actions_section(self, parent):
        """Section actions de capture"""
        actions_frame = ttk.LabelFrame(parent, text="📸 Actions", padding=10)
        actions_frame.pack(fill=tk.X, pady=5)
        
        self.capture_btn = ttk.Button(actions_frame, text="📸 Capturer Photo Haute Résolution", 
                                     command=self.capture_photo, state=tk.DISABLED)
        self.capture_btn.pack(fill=tk.X, pady=2)
        
        # Boutons de sauvegarde
        save_frame = ttk.Frame(actions_frame)
        save_frame.pack(fill=tk.X, pady=5)
        
        self.save_btn = ttk.Button(save_frame, text="💾 Sauvegarder (choisir)", 
                                  command=self.save_photo, state=tk.DISABLED)
        self.save_btn.pack(side=tk.LEFT, padx=2, fill=tk.X, expand=True)
        
        self.quick_save_btn = ttk.Button(save_frame, text="📁 Sauvegarde Rapide", 
                                        command=self.quick_save_photo, state=tk.DISABLED)
        self.quick_save_btn.pack(side=tk.LEFT, padx=2, fill=tk.X, expand=True)
        
        # Info dossier
        folder_info = f"Dossier rapide:\n{self.save_directory}"
        ttk.Label(actions_frame, text=folder_info, foreground="blue", 
                 font=('Arial', 8)).pack(pady=5)
        
        # Prévisualisation rapide
        ttk.Label(actions_frame, text="Aperçu:").pack(pady=5)
        self.preview_label = ttk.Label(actions_frame, text="")
        self.preview_label.pack()
        
        # Espace en bas
        ttk.Label(actions_frame, text="").pack(pady=10)
        
    def update_params(self, event=None):
        """Met à jour tous les paramètres"""
        self.lower_green = np.array([self.hue_min.get(), self.sat_min.get(), self.val_min.get()])
        self.upper_green = np.array([self.hue_max.get(), 255, 255])
        
    def reset_parameters(self):
        """Réinitialise tous les paramètres aux valeurs par défaut"""
        self.hue_min.set(35)
        self.hue_max.set(85)
        self.sat_min.set(40)
        self.val_min.set(40)
        self.erode_var.set(1)
        self.dilate_var.set(1)
        self.blur_var.set(3)
        self.edge_threshold_var.set(128)
        self.matting_strength_var.set(50)
        self.show_mask_var.set(False)
        self.show_edges_var.set(False)
        self.update_params()
        
    def start_camera(self):
        if not self.is_running:
            self.camera = cv2.VideoCapture(0)
            # Configurer pour Logitech C270 HD
            self.camera.set(cv2.CAP_PROP_FRAME_WIDTH, 1280)
            self.camera.set(cv2.CAP_PROP_FRAME_HEIGHT, 720)
            self.camera.set(cv2.CAP_PROP_FPS, 30)
            
            if self.camera.isOpened():
                self.is_running = True
                self.update_frame()
                self.start_btn.config(state=tk.DISABLED)
                self.stop_btn.config(state=tk.NORMAL)
                self.capture_btn.config(state=tk.NORMAL)
                self.status_bar.config(text="Caméra active - Logitech C270 HD")
            else:
                messagebox.showerror("Erreur", "Impossible d'ouvrir la caméra")
    
    def stop_camera(self):
        self.is_running = False
        if self.camera:
            self.camera.release()
        self.video_label.config(image='')
        self.start_btn.config(state=tk.NORMAL)
        self.stop_btn.config(state=tk.DISABLED)
        self.capture_btn.config(state=tk.DISABLED)
        self.save_btn.config(state=tk.DISABLED)
        self.quick_save_btn.config(state=tk.DISABLED)
        self.status_bar.config(text="Caméra arrêtée")
    
    def load_background(self):
        file_path = filedialog.askopenfilename(
            title="Choisir une image de fond",
            filetypes=[("Image files", "*.png *.jpg *.jpeg *.bmp"), ("All files", "*.*")]
        )
        if file_path:
            try:
                self.background_image = cv2.imread(file_path, cv2.IMREAD_UNCHANGED)
                if self.background_image is None:
                    raise Exception("Image invalide")
                
                self.background_path = file_path
                filename = os.path.basename(file_path)
                self.bg_label.config(text=f"✓ {filename[:30]}...", foreground="green")
                self.status_bar.config(text=f"Fond chargé: {filename}")
                
                messagebox.showinfo("Succès", "Image de fond chargée avec succès!")
            except Exception as e:
                messagebox.showerror("Erreur", f"Impossible de charger l'image: {str(e)}")
                self.background_path = None
                self.bg_label.config(text="Erreur de chargement", foreground="red")
    
    def load_overlay(self):
        file_path = filedialog.askopenfilename(
            title="Choisir une image PNG pour le premier plan",
            filetypes=[("PNG files", "*.png"), ("All files", "*.*")]
        )
        if file_path:
            try:
                self.overlay_image = cv2.imread(file_path, cv2.IMREAD_UNCHANGED)
                if self.overlay_image is None:
                    raise Exception("Image invalide")
                
                self.overlay_path = file_path
                filename = os.path.basename(file_path)
                self.overlay_label.config(text=f"✓ {filename[:30]}...", foreground="green")
                
                # Ajuster les sliders de position en fonction de la taille de l'image
                if self.current_frame is not None:
                    h, w = self.current_frame.shape[:2]
                    self.overlay_x.config(to=max(0, w - self.overlay_image.shape[1]))
                    self.overlay_y.config(to=max(0, h - self.overlay_image.shape[0]))
                
                self.status_bar.config(text=f"Overlay chargé: {filename}")
                
                messagebox.showinfo("Succès", "Image de premier plan chargée avec succès!")
            except Exception as e:
                messagebox.showerror("Erreur", f"Impossible de charger l'image: {str(e)}")
                self.overlay_path = None
                self.overlay_label.config(text="Erreur de chargement", foreground="red")
    
    def create_refined_mask(self, mask):
        """Crée un masque raffiné avec des bords doux"""
        # Appliquer érosion et dilatation
        kernel = np.ones((3, 3), np.uint8)
        
        if self.erode_var.get() > 0:
            mask = cv2.erode(mask, kernel, iterations=self.erode_var.get())
        
        if self.dilate_var.get() > 0:
            mask = cv2.dilate(mask, kernel, iterations=self.dilate_var.get())
        
        # Appliquer un flou pour adoucir les bords
        if self.blur_var.get() > 1:
            blur_size = self.blur_var.get()
            if blur_size % 2 == 0:
                blur_size += 1
            mask = cv2.GaussianBlur(mask, (blur_size, blur_size), 0)
        
        return mask
    
    def apply_overlay(self, frame):
        """Applique l'image de premier plan (overlay) sur l'image"""
        if self.overlay_image is None:
            return frame
        
        h, w = frame.shape[:2]
        overlay_h, overlay_w = self.overlay_image.shape[:2]
        
        # S'assurer que l'overlay ne dépasse pas de l'image
        x = min(self.overlay_position[0], max(0, w - overlay_w))
        y = min(self.overlay_position[1], max(0, h - overlay_h))
        
        # Créer une copie de l'image
        result = frame.copy()
        
        if self.overlay_image.shape[2] == 4:  # PNG avec transparence
            # Extraire les canaux
            overlay_rgb = self.overlay_image[:, :, :3]
            overlay_alpha = self.overlay_image[:, :, 3] / 255.0 * self.overlay_opacity
            
            # Région d'intérêt
            roi = result[y:y+overlay_h, x:x+overlay_w]
            
            # Mélange avec prise en compte de la transparence
            for c in range(3):
                roi[:, :, c] = (overlay_rgb[:, :, c] * overlay_alpha + 
                               roi[:, :, c] * (1 - overlay_alpha))
            
            result[y:y+overlay_h, x:x+overlay_w] = roi
        else:
            # Overlay sans transparence (opacité simple)
            overlay_resized = cv2.resize(self.overlay_image, (overlay_w, overlay_h))
            roi = result[y:y+overlay_h, x:x+overlay_w]
            cv2.addWeighted(overlay_resized, self.overlay_opacity, roi, 
                           1 - self.overlay_opacity, 0, roi)
        
        return result
    
    def apply_chroma_key(self, frame):
        if self.background_image is None:
            return frame
        
        # Redimensionner le fond à la taille exacte de la frame
        h, w = frame.shape[:2]
        bg_resized = cv2.resize(self.background_image, (w, h))
        
        # Convertir en HSV pour la détection du vert
        hsv = cv2.cvtColor(frame, cv2.COLOR_BGR2HSV)
        
        # Créer le masque initial
        initial_mask = cv2.inRange(hsv, self.lower_green, self.upper_green)
        
        # Raffiner le masque
        refined_mask = self.create_refined_mask(initial_mask)
        
        # Appliquer le matting si activé
        if self.matting_strength_var.get() > 0:
            refined_mask = self.apply_edge_matting(refined_mask, frame)
        
        # Options d'affichage debug
        if self.show_mask_var.get():
            return cv2.cvtColor(refined_mask, cv2.COLOR_GRAY2BGR)
        
        if self.show_edges_var.get():
            edges = cv2.Canny(refined_mask, 50, 150)
            return cv2.cvtColor(edges, cv2.COLOR_GRAY2BGR)
        
        # Convertir le masque en 3 canaux
        mask_3channel = cv2.cvtColor(refined_mask, cv2.COLOR_GRAY2BGR) / 255.0
        
        # Gestion de l'image de fond avec transparence
        if bg_resized.shape[2] == 4:  # PNG avec canal alpha
            # Extraire les canaux
            bg_bgr = bg_resized[:, :, :3]
            alpha = bg_resized[:, :, 3] / 255.0
            
            # Composition avec matting avancé
            result = np.zeros_like(frame, dtype=np.float32)
            frame_float = frame.astype(np.float32)
            bg_float = bg_bgr.astype(np.float32)
            
            # Zones du premier plan (personne filmée)
            fg_mask = 1.0 - mask_3channel
            
            # Combinaison pondérée
            for c in range(3):
                result[:, :, c] = (frame_float[:, :, c] * fg_mask[:, :, c] + 
                                  bg_float[:, :, c] * mask_3channel[:, :, c] * alpha +
                                  frame_float[:, :, c] * (1 - alpha))
            
            result = np.clip(result, 0, 255).astype(np.uint8)
            
        else:  # Image sans transparence
            bg_bgr = bg_resized
            frame_float = frame.astype(np.float32)
            bg_float = bg_bgr.astype(np.float32)
            
            # Composition simple
            result = (frame_float * (1.0 - mask_3channel) + bg_float * mask_3channel).astype(np.uint8)
        
        # Appliquer l'overlay si présent
        if self.overlay_image is not None:
            result = self.apply_overlay(result)
        
        return result
    
    def apply_edge_matting(self, mask, frame):
        """Applique un matting pour des transitions plus douces sur les bords"""
        # Calculer la distance par rapport au bord
        dist_transform = cv2.distanceTransform(mask, cv2.DIST_L2, 5)
        dist_transform = cv2.normalize(dist_transform, None, 0, 255, cv2.NORM_MINMAX).astype(np.uint8)
        
        # Créer un masque de bord
        edges = cv2.Canny(mask, 50, 150)
        
        # Appliquer la transparence sur les bords en fonction de la force du matting
        strength = self.matting_strength_var.get() / 100.0
        edge_mask = cv2.dilate(edges, np.ones((3, 3), np.uint8), iterations=2)
        
        # Rendre les bords semi-transparents
        mask_float = mask.astype(np.float32) / 255.0
        edge_mask_float = edge_mask.astype(np.float32) / 255.0
        
        # Adoucir les bords
        mask_float = mask_float * (1 - edge_mask_float * strength) + dist_transform.astype(np.float32) / 255.0 * edge_mask_float * strength
        
        return (mask_float * 255).astype(np.uint8)
    
    def update_frame(self):
        if self.is_running:
            ret, frame = self.camera.read()
            if ret:
                # Appliquer le chroma key
                processed_frame = self.apply_chroma_key(frame)
                self.current_frame = processed_frame.copy()
                
                # Convertir pour affichage
                rgb_frame = cv2.cvtColor(processed_frame, cv2.COLOR_BGR2RGB)
                pil_image = Image.fromarray(rgb_frame)
                
                # Redimensionner pour l'affichage
                display_size = (800, 600)
                pil_image.thumbnail(display_size, Image.Resampling.LANCZOS)
                
                # Convertir pour tkinter
                tk_image = ImageTk.PhotoImage(pil_image)
                self.video_label.config(image=tk_image)
                self.video_label.image = tk_image
                
                # Mettre à jour les limites des sliders de position overlay
                if self.overlay_image is not None:
                    h, w = frame.shape[:2]
                    self.overlay_x.config(to=max(0, w - self.overlay_image.shape[1]))
                    self.overlay_y.config(to=max(0, h - self.overlay_image.shape[0]))
            
            self.root.after(10, self.update_frame)
    
    def capture_photo(self):
        if self.current_frame is not None:
            # Capturer en haute résolution
            ret, high_res_frame = self.camera.read()
            if ret:
                self.captured_photo = self.apply_chroma_key(high_res_frame)
                
                # Mettre à jour l'aperçu
                rgb_preview = cv2.cvtColor(self.captured_photo, cv2.COLOR_BGR2RGB)
                pil_preview = Image.fromarray(rgb_preview)
                pil_preview.thumbnail((150, 150))
                tk_preview = ImageTk.PhotoImage(pil_preview)
                self.preview_label.config(image=tk_preview)
                self.preview_label.image = tk_preview
                
                self.save_btn.config(state=tk.NORMAL)
                self.quick_save_btn.config(state=tk.NORMAL)
                self.status_bar.config(text="Photo haute résolution capturée")
            else:
                messagebox.showerror("Erreur", "Impossible de capturer en haute résolution")
    
    def quick_save_photo(self):
        """Sauvegarde rapide dans le dossier prédéfini"""
        if hasattr(self, 'captured_photo'):
            try:
                # Générer un nom de fichier avec timestamp
                from datetime import datetime
                timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
                filename = f"chroma_key_{timestamp}.png"
                file_path = self.save_directory / filename
                
                cv2.imwrite(str(file_path), self.captured_photo)
                self.status_bar.config(text=f"Photo sauvegardée: {filename}")
                messagebox.showinfo("Succès", f"Photo sauvegardée dans:\n{file_path}")
            except Exception as e:
                messagebox.showerror("Erreur", f"Erreur lors de la sauvegarde: {str(e)}")
        else:
            messagebox.showwarning("Attention", "Aucune photo à sauvegarder")
    
    def save_photo(self):
        """Sauvegarde avec choix de l'emplacement"""
        if hasattr(self, 'captured_photo'):
            # Générer un nom de fichier avec timestamp
            from datetime import datetime
            timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
            default_name = f"chroma_key_{timestamp}.png"
            
            file_path = filedialog.asksaveasfilename(
                defaultextension=".png",
                initialfile=default_name,
                initialdir=str(self.save_directory),
                filetypes=[("PNG files", "*.png"), ("JPEG files", "*.jpg"), ("All files", "*.*")]
            )
            if file_path:
                cv2.imwrite(file_path, self.captured_photo)
                self.status_bar.config(text=f"Photo sauvegardée: {os.path.basename(file_path)}")
                messagebox.showinfo("Succès", f"Photo sauvegardée avec succès!")
        else:
            messagebox.showwarning("Attention", "Aucune photo à sauvegarder")

if __name__ == "__main__":
    root = tk.Tk()
    app = ChromaKeyApp(root)
    root.mainloop()
