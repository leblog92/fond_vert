import tkinter as tk
from tkinter import ttk, messagebox
import cv2
from PIL import Image, ImageTk
import numpy as np
import os
from pathlib import Path
import threading
import time
from dataclasses import dataclass
import json

@dataclass
class SetConfig:
    """Configuration pour chaque set (fond + premier plan)"""
    fond_file: str
    pp_file: str
    largeur: int
    hauteur: int
    zone_visible: tuple  # (largeur, hauteur, pos_x, pos_y)
    
class SalonBDApp:
    def __init__(self, root):
        self.root = root
        self.root.title("Salon BD - Photomaton")
        self.root.geometry("1400x800")
        
        # Configuration des dossiers
        self.images_dir = Path(__file__).parent / "images"
        self.output_dir = Path(os.environ['USERPROFILE']) / "Images" / "SalonBD"
        self.output_dir.mkdir(exist_ok=True)
        
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
        self.adjust_x = tk.DoubleVar(value=0)
        self.adjust_y = tk.DoubleVar(value=0)
        self.zoom_factor = tk.DoubleVar(value=1.0)
        
        # Charger les images de fond et premier plan
        self.load_backgrounds()
        
        # Initialiser l'interface
        self.setup_ui()
        
        # Démarrer la caméra
        self.start_camera()
        
    def load_backgrounds(self):
        """Charge les images de fond et premier plan"""
        self.fonds = {}
        self.pps = {}
        
        for set_name, config in self.sets.items():
            fond_path = self.images_dir / config.fond_file
            pp_path = self.images_dir / config.pp_file
            
            if fond_path.exists():
                self.fonds[set_name] = cv2.imread(str(fond_path))
                self.fonds[set_name] = cv2.cvtColor(self.fonds[set_name], cv2.COLOR_BGR2RGB)
            else:
                print(f"Fichier non trouvé: {fond_path}")
                
            if pp_path.exists():
                self.pps[set_name] = cv2.imread(str(pp_path))
                self.pps[set_name] = cv2.cvtColor(self.pps[set_name], cv2.COLOR_BGR2RGB)
            else:
                print(f"Fichier non trouvé: {pp_path}")
    
    def setup_ui(self):
        """Configure l'interface utilisateur"""
        # Frame principal
        main_frame = ttk.Frame(self.root, padding="10")
        main_frame.grid(row=0, column=0, sticky=(tk.W, tk.E, tk.N, tk.S))
        
        # Panneau de contrôle gauche
        control_frame = ttk.LabelFrame(main_frame, text="Contrôles", padding="10")
        control_frame.grid(row=0, column=0, sticky=(tk.W, tk.E, tk.N, tk.S), padx=(0, 10))
        
        # Sélection du set
        ttk.Label(control_frame, text="Set:").grid(row=0, column=0, sticky=tk.W, pady=5)
        set_combo = ttk.Combobox(control_frame, textvariable=self.current_set, 
                                 values=list(self.sets.keys()), state="readonly")
        set_combo.grid(row=0, column=1, sticky=(tk.W, tk.E), pady=5)
        set_combo.bind('<<ComboboxSelected>>', self.on_set_change)
        
        # Ajustements position
        ttk.Label(control_frame, text="Ajustement X:").grid(row=1, column=0, sticky=tk.W, pady=5)
        x_scale = ttk.Scale(control_frame, from_=-200, to=200, orient=tk.HORIZONTAL,
                           variable=self.adjust_x, command=self.update_preview)
        x_scale.grid(row=1, column=1, sticky=(tk.W, tk.E), pady=5)
        
        ttk.Label(control_frame, text="Ajustement Y:").grid(row=2, column=0, sticky=tk.W, pady=5)
        y_scale = ttk.Scale(control_frame, from_=-200, to=200, orient=tk.HORIZONTAL,
                           variable=self.adjust_y, command=self.update_preview)
        y_scale.grid(row=2, column=1, sticky=(tk.W, tk.E), pady=5)
        
        # Zoom
        ttk.Label(control_frame, text="Zoom:").grid(row=3, column=0, sticky=tk.W, pady=5)
        zoom_scale = ttk.Scale(control_frame, from_=0.5, to=2.0, orient=tk.HORIZONTAL,
                              variable=self.zoom_factor, command=self.update_preview)
        zoom_scale.grid(row=3, column=1, sticky=(tk.W, tk.E), pady=5)
        
        # Informations set
        self.info_text = tk.Text(control_frame, height=8, width=30, state=tk.DISABLED)
        self.info_text.grid(row=4, column=0, columnspan=2, pady=10)
        
        # Bouton de capture
        capture_btn = ttk.Button(control_frame, text="📸 Prendre la photo", 
                                 command=self.capture_photo)
        capture_btn.grid(row=5, column=0, columnspan=2, pady=10)
        
        # Frame pour l'aperçu
        preview_frame = ttk.LabelFrame(main_frame, text="Aperçu", padding="10")
        preview_frame.grid(row=0, column=1, sticky=(tk.W, tk.E, tk.N, tk.S))
        
        # Canvas pour l'aperçu
        self.preview_canvas = tk.Canvas(preview_frame, width=800, height=600, bg='gray')
        self.preview_canvas.grid(row=0, column=0)
        
        # Label pour l'image de la caméra brute
        camera_frame = ttk.LabelFrame(main_frame, text="Caméra", padding="10")
        camera_frame.grid(row=0, column=2, sticky=(tk.W, tk.E, tk.N, tk.S), padx=(10, 0))
        
        self.camera_label = ttk.Label(camera_frame)
        self.camera_label.grid(row=0, column=0)
        
        # Mettre à jour les informations du set
        self.update_set_info()
    
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
        """Démarre la caméra Iriun"""
        try:
            # Iriun crée généralement une caméra virtuelle accessible via l'index 1 ou 2
            # Vous pouvez ajuster l'index si nécessaire
            self.camera = cv2.VideoCapture(1)  # Essayez 0, 1, ou 2 selon configuration
            
            if not self.camera.isOpened():
                # Essayer avec d'autres indices
                for i in [2, 0]:
                    self.camera = cv2.VideoCapture(i)
                    if self.camera.isOpened():
                        break
            
            if self.camera.isOpened():
                self.camera_running = True
                # Définir la résolution souhaitée
                self.camera.set(cv2.CAP_PROP_FRAME_WIDTH, 1932)
                self.camera.set(cv2.CAP_PROP_FRAME_HEIGHT, 2576)
                self.update_camera()
            else:
                messagebox.showerror("Erreur", "Impossible d'ouvrir la caméra Iriun")
        except Exception as e:
            messagebox.showerror("Erreur", f"Erreur caméra: {str(e)}")
    
    def update_camera(self):
        """Met à jour l'affichage de la caméra"""
        if self.camera_running and self.camera:
            ret, frame = self.camera.read()
            if ret:
                # Redimensionner pour l'affichage
                frame_resized = cv2.resize(frame, (400, 533))  # Ratio 3:4 approximatif
                frame_rgb = cv2.cvtColor(frame_resized, cv2.COLOR_BGR2RGB)
                
                # Convertir en ImageTk
                img = Image.fromarray(frame_rgb)
                imgtk = ImageTk.PhotoImage(image=img)
                
                # Mettre à jour le label
                self.camera_label.imgtk = imgtk
                self.camera_label.configure(image=imgtk)
                
                # Mettre à jour l'aperçu
                self.update_preview(frame)
            
            # Planifier la prochaine mise à jour
            self.root.after(30, self.update_camera)
    
    def update_preview(self, event=None, camera_frame=None):
        """Met à jour l'aperçu avec la composition"""
        if camera_frame is None and self.camera_running and self.camera:
            ret, camera_frame = self.camera.read()
            if not ret:
                return
        
        if camera_frame is not None:
            set_name = self.current_set.get()
            config = self.sets[set_name]
            
            # Créer la composition
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
                
                # Mettre à jour le canvas
                self.preview_canvas.delete("all")
                self.preview_canvas.create_image(400, 300, image=imgtk, anchor=tk.CENTER)
                self.preview_canvas.imgtk = imgtk
    
    def create_composition(self, camera_frame, set_name):
        """Crée la composition finale"""
        config = self.sets[set_name]
        
        # Vérifier que les images existent
        if set_name not in self.fonds or set_name not in self.pps:
            return None
        
        fond = self.fonds[set_name].copy()
        pp = self.pps[set_name]
        
        # Redimensionner la caméra pour correspondre à la zone visible
        zone_w, zone_h, zone_x, zone_y = config.zone_visible
        
        # Ajuster la taille de la caméra avec le zoom
        zoom = self.zoom_factor.get()
        new_h = int(zone_h * zoom)
        new_w = int(zone_w * zoom)
        
        camera_resized = cv2.resize(camera_frame, (new_w, new_h))
        
        # Appliquer le détourage fond vert (simplifié - à ajuster selon votre éclairage)
        # Convertir en HSV pour meilleure détection du vert
        hsv = cv2.cvtColor(camera_resized, cv2.COLOR_RGB2HSV)
        
        # Plage de vert à ajuster selon votre fond
        lower_green = np.array([40, 40, 40])
        upper_green = np.array([80, 255, 255])
        
        # Créer un masque pour le fond vert
        mask = cv2.inRange(hsv, lower_green, upper_green)
        mask_inv = cv2.bitwise_not(mask)
        
        # Extraire la personne (tout ce qui n'est pas vert)
        person = cv2.bitwise_and(camera_resized, camera_resized, mask=mask_inv)
        
        # Calculer la position avec ajustements
        center_x = zone_x + (zone_w - new_w) // 2 + int(self.adjust_x.get())
        center_y = zone_y + (zone_h - new_h) // 2 + int(self.adjust_y.get())
        
        # S'assurer que la position est dans les limites
        center_x = max(0, min(center_x, fond.shape[1] - new_w))
        center_y = max(0, min(center_y, fond.shape[0] - new_h))
        
        # Superposer la personne sur le fond
        roi = fond[center_y:center_y+new_h, center_x:center_x+new_w]
        
        # Zones où la personne est présente
        person_mask = mask_inv / 255.0
        person_mask = np.stack([person_mask] * 3, axis=2)
        
        # Mélanger
        blended = roi * (1 - person_mask) + person * person_mask
        blended = blended.astype(np.uint8)
        
        fond[center_y:center_y+new_h, center_x:center_x+new_w] = blended
        
        # Superposer le premier plan (avec transparence)
        # Note: Cette partie suppose que le premier plan a un fond transparent
        # Si ce n'est pas le cas, il faudra adapter
        if pp.shape[2] == 4:  # Si RGBA
            alpha = pp[:, :, 3] / 255.0
            for c in range(3):
                fond[:pp.shape[0], :pp.shape[1], c] = \
                    fond[:pp.shape[0], :pp.shape[1], c] * (1 - alpha) + \
                    pp[:, :, c] * alpha
        else:
            # Si pas de transparence, on superpose simplement
            h, w = pp.shape[:2]
            fond[:h, :w] = pp
        
        return fond
    
    def capture_photo(self):
        """Capture et enregistre la photo"""
        if not self.camera_running or not self.camera:
            messagebox.showerror("Erreur", "Caméra non disponible")
            return
        
        ret, camera_frame = self.camera.read()
        if not ret:
            messagebox.showerror("Erreur", "Impossible de capturer l'image")
            return
        
        set_name = self.current_set.get()
        composed = self.create_composition(camera_frame, set_name)
        
        if composed is not None:
            # Générer un nom de fichier avec horodatage
            timestamp = time.strftime("%Y%m%d_%H%M%S")
            filename = f"salon_bd_{set_name.replace(' ', '')}_{timestamp}.png"
            filepath = self.output_dir / filename
            
            # Sauvegarder
            composed_bgr = cv2.cvtColor(composed, cv2.COLOR_RGB2BGR)
            cv2.imwrite(str(filepath), composed_bgr)
            
            messagebox.showinfo("Succès", f"Photo enregistrée :\n{filepath}")
    
    def __del__(self):
        """Nettoyage à la fermeture"""
        if self.camera:
            self.camera_running = False
            self.camera.release()

def main():
    root = tk.Tk()
    app = SalonBDApp(root)
    root.mainloop()

if __name__ == "__main__":
    main()