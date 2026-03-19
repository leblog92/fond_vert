import tkinter as tk
from tkinter import ttk, messagebox, filedialog
import cv2
import numpy as np
from PIL import Image, ImageTk, ImageDraw
import os
import pandas as pd
from pathlib import Path
import subprocess
import platform
from datetime import datetime
import piexif
import piexif.helper

class GreenScreenApp:
    def __init__(self, root):
        self.root = root
        self.root.title("Studio Photo Fond Vert - Salon BD")
        self.root.geometry("1400x900")
        
        # Variables
        self.camera_index = tk.IntVar(value=0)
        self.cameras = []
        self.camera_running = False
        self.cap = None
        self.current_set = tk.StringVar(value="set 1")
        self.photo_name = tk.StringVar()
        self.email = tk.StringVar()
        
        # Paramètres de détourage
        self.lower_green = np.array([35, 50, 50])
        self.upper_green = np.array([85, 255, 255])
        self.blur_value = tk.IntVar(value=5)
        self.threshold_value = tk.IntVar(value=40)
        self.morph_value = tk.IntVar(value=3)
        
        # Position de la personne dans la zone visible
        self.person_x = tk.IntVar(value=0)
        self.person_y = tk.IntVar(value=0)
        
        # Charger les données du fichier Excel
        self.load_set_data()
        
        # Dossier de sauvegarde
        self.save_dir = Path(os.environ['USERPROFILE']) / "Pictures" / "salonBD"
        self.save_dir.mkdir(parents=True, exist_ok=True)
        
        # Images de fond et premier plan
        self.background_img = None
        self.foreground_img = None
        self.background_tk = None
        self.foreground_tk = None
        
        self.create_widgets()
        self.scan_cameras()
        
    def load_set_data(self):
        """Charge les données des sets depuis le fichier Excel"""
        try:
            df = pd.read_excel('data.xlsx', sheet_name='Feuil1', skiprows=3)
            self.sets_data = {}
            for _, row in df.iterrows():
                set_name = row.iloc[0].lower().replace(' ', '')
                self.sets_data[set_name] = {
                    'background': row.iloc[1],
                    'foreground': row.iloc[2],
                    'bg_width': row.iloc[3],
                    'bg_height': row.iloc[4],
                    'visible_width': row.iloc[5],
                    'visible_height': row.iloc[6],
                    'visible_x': row.iloc[7],
                    'visible_y': row.iloc[8]
                }
        except Exception as e:
            print(f"Erreur chargement Excel: {e}")
            # Données par défaut
            self.sets_data = {
                'set1': {'background': 'fond1.png', 'foreground': 'pp1.png', 'bg_width': 2000, 'bg_height': 1688, 
                        'visible_width': 1061, 'visible_height': 597, 'visible_x': -80, 'visible_y': 959},
                'set2': {'background': 'fond2.png', 'foreground': 'pp2.png', 'bg_width': 2000, 'bg_height': 1414,
                        'visible_width': 2286, 'visible_height': 1286, 'visible_x': -137, 'visible_y': 68},
                'set3': {'background': 'fond3.png', 'foreground': 'pp3.png', 'bg_width': 2000, 'bg_height': 2632,
                        'visible_width': 1267, 'visible_height': 711, 'visible_x': 942, 'visible_y': 1713},
                'set4': {'background': 'fond4.png', 'foreground': 'pp4.png', 'bg_width': 2000, 'bg_height': 2633,
                        'visible_width': 1890, 'visible_height': 1063, 'visible_x': 74, 'visible_y': 1253}
            }
    
    def create_widgets(self):
        # Frame principal
        main_frame = ttk.Frame(self.root, padding="10")
        main_frame.grid(row=0, column=0, sticky=(tk.W, tk.E, tk.N, tk.S))
        
        # Frame contrôle gauche
        control_frame = ttk.LabelFrame(main_frame, text="Contrôles", padding="10")
        control_frame.grid(row=0, column=0, sticky=(tk.W, tk.E, tk.N, tk.S), padx=5)
        
        # Sélection caméra
        ttk.Label(control_frame, text="Caméra:").grid(row=0, column=0, sticky=tk.W, pady=5)
        self.camera_combo = ttk.Combobox(control_frame, textvariable=self.camera_index, width=30)
        self.camera_combo.grid(row=0, column=1, pady=5)
        
        ttk.Button(control_frame, text="Scanner caméras", command=self.scan_cameras).grid(row=1, column=0, columnspan=2, pady=5)
        
        # Boutons caméra
        btn_frame = ttk.Frame(control_frame)
        btn_frame.grid(row=2, column=0, columnspan=2, pady=10)
        ttk.Button(btn_frame, text="Démarrer", command=self.start_camera).pack(side=tk.LEFT, padx=5)
        ttk.Button(btn_frame, text="Arrêter", command=self.stop_camera).pack(side=tk.LEFT, padx=5)
        
        # Sélection set
        ttk.Label(control_frame, text="Set:").grid(row=3, column=0, sticky=tk.W, pady=5)
        set_combo = ttk.Combobox(control_frame, textvariable=self.current_set, 
                                values=['set 1', 'set 2', 'set 3', 'set 4'], width=30)
        set_combo.grid(row=3, column=1, pady=5)
        set_combo.bind('<<ComboboxSelected>>', self.on_set_change)
        
        # Paramètres détourage
        ttk.Label(control_frame, text="PARAMÈTRES DÉTOURAGE", font=('Arial', 10, 'bold')).grid(row=4, column=0, columnspan=2, pady=10)
        
        ttk.Label(control_frame, text="Flou:").grid(row=5, column=0, sticky=tk.W)
        ttk.Scale(control_frame, from_=1, to=21, variable=self.blur_value, orient=tk.HORIZONTAL, length=200).grid(row=5, column=1)
        ttk.Label(control_frame, textvariable=self.blur_value).grid(row=5, column=2)
        
        ttk.Label(control_frame, text="Seuil:").grid(row=6, column=0, sticky=tk.W)
        ttk.Scale(control_frame, from_=20, to=100, variable=self.threshold_value, orient=tk.HORIZONTAL, length=200).grid(row=6, column=1)
        ttk.Label(control_frame, textvariable=self.threshold_value).grid(row=6, column=2)
        
        ttk.Label(control_frame, text="Morphologie:").grid(row=7, column=0, sticky=tk.W)
        ttk.Scale(control_frame, from_=1, to=10, variable=self.morph_value, orient=tk.HORIZONTAL, length=200).grid(row=7, column=1)
        ttk.Label(control_frame, textvariable=self.morph_value).grid(row=7, column=2)
        
        # Position personne
        ttk.Label(control_frame, text="POSITION PERSONNE", font=('Arial', 10, 'bold')).grid(row=8, column=0, columnspan=2, pady=10)
        
        ttk.Label(control_frame, text="X:").grid(row=9, column=0, sticky=tk.W)
        ttk.Scale(control_frame, from_=-500, to=500, variable=self.person_x, orient=tk.HORIZONTAL, length=200).grid(row=9, column=1)
        ttk.Label(control_frame, textvariable=self.person_x).grid(row=9, column=2)
        
        ttk.Label(control_frame, text="Y:").grid(row=10, column=0, sticky=tk.W)
        ttk.Scale(control_frame, from_=-500, to=500, variable=self.person_y, orient=tk.HORIZONTAL, length=200).grid(row=10, column=1)
        ttk.Label(control_frame, textvariable=self.person_y).grid(row=10, column=2)
        
        # Informations personne
        ttk.Label(control_frame, text="INFORMATIONS", font=('Arial', 10, 'bold')).grid(row=11, column=0, columnspan=2, pady=10)
        
        ttk.Label(control_frame, text="Nom:").grid(row=12, column=0, sticky=tk.W)
        ttk.Entry(control_frame, textvariable=self.photo_name, width=30).grid(row=12, column=1, columnspan=2, pady=5)
        
        ttk.Label(control_frame, text="Email:").grid(row=13, column=0, sticky=tk.W)
        ttk.Entry(control_frame, textvariable=self.email, width=30).grid(row=13, column=1, columnspan=2, pady=5)
        
        # Bouton prise de vue
        ttk.Button(control_frame, text="📷 PRENDRE LA PHOTO", command=self.take_photo, 
                  style='Accent.TButton').grid(row=14, column=0, columnspan=3, pady=20)
        
        # Frame visualisation
        view_frame = ttk.LabelFrame(main_frame, text="Aperçu", padding="10")
        view_frame.grid(row=0, column=1, sticky=(tk.W, tk.E, tk.N, tk.S), padx=5)
        
        # Canvas pour l'aperçu
        self.canvas = tk.Canvas(view_frame, width=800, height=600, bg='black')
        self.canvas.grid(row=0, column=0)
        
        # Labels pour les images
        self.background_label = ttk.Label(view_frame)
        self.background_label.grid(row=1, column=0, pady=5)
        
        self.foreground_label = ttk.Label(view_frame)
        self.foreground_label.grid(row=2, column=0, pady=5)
        
        # Charger le premier set
        self.on_set_change()
    
    def scan_cameras(self):
        """Scanne les caméras disponibles"""
        self.cameras = []
        for i in range(10):
            cap = cv2.VideoCapture(i, cv2.CAP_DSHOW)
            if cap.isOpened():
                self.cameras.append(f"Caméra {i}")
                cap.release()
        
        if self.cameras:
            self.camera_combo['values'] = self.cameras
            self.camera_index.set(0)
        else:
            self.camera_combo['values'] = ['Aucune caméra trouvée']
            messagebox.showwarning("Attention", "Aucune caméra détectée")
    
    def start_camera(self):
        """Démarre la caméra"""
        if not self.camera_running:
            try:
                self.cap = cv2.VideoCapture(self.camera_index.get(), cv2.CAP_DSHOW)
                self.cap.set(cv2.CAP_PROP_FRAME_WIDTH, 1280)
                self.cap.set(cv2.CAP_PROP_FRAME_HEIGHT, 720)
                
                if self.cap.isOpened():
                    self.camera_running = True
                    self.update_frame()
            except Exception as e:
                messagebox.showerror("Erreur", f"Impossible de démarrer la caméra: {e}")
    
    def stop_camera(self):
        """Arrête la caméra"""
        if self.camera_running and self.cap:
            self.camera_running = False
            self.cap.release()
            self.canvas.delete("all")
    
    def update_frame(self):
        """Met à jour l'aperçu de la caméra"""
        if self.camera_running and self.cap:
            ret, frame = self.cap.read()
            if ret:
                # Traitement fond vert
                processed = self.process_greenscreen(frame)
                
                # Redimensionner pour l'affichage
                display = cv2.resize(processed, (800, 600))
                
                # Convertir pour Tkinter
                img = cv2.cvtColor(display, cv2.COLOR_BGR2RGB)
                img = Image.fromarray(img)
                img_tk = ImageTk.PhotoImage(img)
                
                self.canvas.create_image(400, 300, image=img_tk)
                self.canvas.image = img_tk
            
            self.root.after(30, self.update_frame)
    
    def process_greenscreen(self, frame):
        """Traite l'image pour enlever le fond vert"""
        # Convertir en HSV
        hsv = cv2.cvtColor(frame, cv2.COLOR_BGR2HSV)
        
        # Ajuster les paramètres selon les sliders
        lower = np.array([35, self.threshold_value.get(), 50])
        upper = np.array([85, 255, 255])
        
        # Créer le masque
        mask = cv2.inRange(hsv, lower, upper)
        
        # Nettoyer le masque
        blur = self.blur_value.get()
        if blur % 2 == 0:
            blur += 1
        mask = cv2.medianBlur(mask, blur)
        
        kernel = np.ones((self.morph_value.get(), self.morph_value.get()), np.uint8)
        mask = cv2.morphologyEx(mask, cv2.MORPH_CLOSE, kernel)
        mask = cv2.morphologyEx(mask, cv2.MORPH_OPEN, kernel)
        
        # Inverser le masque pour garder la personne
        mask_inv = cv2.bitwise_not(mask)
        
        # Appliquer le masque
        result = cv2.bitwise_and(frame, frame, mask=mask_inv)
        
        return result
    
    def on_set_change(self, event=None):
        """Change le set actuel"""
        set_key = self.current_set.get().lower().replace(' ', '')
        if set_key in self.sets_data:
            data = self.sets_data[set_key]
            
            # Charger et afficher le fond
            if os.path.exists(data['background']):
                bg = Image.open(data['background'])
                bg.thumbnail((200, 150))
                self.background_tk = ImageTk.PhotoImage(bg)
                self.background_label.config(image=self.background_tk, text="")
            else:
                self.background_label.config(text=f"Fond: {data['background']} (non trouvé)")
            
            # Charger et afficher le premier plan
            if os.path.exists(data['foreground']):
                fg = Image.open(data['foreground'])
                fg.thumbnail((200, 150))
                self.foreground_tk = ImageTk.PhotoImage(fg)
                self.foreground_label.config(image=self.foreground_tk, text="")
            else:
                self.foreground_label.config(text=f"PP: {data['foreground']} (non trouvé)")
    
    def take_photo(self):
        """Prend une photo et l'enregistre"""
        if not self.camera_running:
            messagebox.showwarning("Attention", "Veuillez démarrer la caméra")
            return
        
        if not self.photo_name.get():
            messagebox.showwarning("Attention", "Veuillez entrer un nom")
            return
        
        if not self.email.get():
            messagebox.showwarning("Attention", "Veuillez entrer une adresse email")
            return
        
        # Capturer l'image
        ret, frame = self.cap.read()
        if ret:
            # Traiter l'image
            processed = self.process_greenscreen(frame)
            
            # Appliquer le fond et le premier plan
            final_image = self.compose_with_background(processed)
            
            # Générer le nom de fichier
            timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
            name_clean = self.photo_name.get().replace(' ', '_')
            filename = f"{name_clean}_{timestamp}.jpg"
            filepath = self.save_dir / filename
            
            # Sauvegarder avec métadonnées
            self.save_image_with_metadata(final_image, filepath)
            
            messagebox.showinfo("Succès", f"Photo enregistrée dans:\n{filepath}")
    
    def compose_with_background(self, person_img):
        """Compose l'image avec le fond et le premier plan"""
        set_key = self.current_set.get().lower().replace(' ', '')
        data = self.sets_data[set_key]
        
        # Charger le fond
        if os.path.exists(data['background']):
            background = Image.open(data['background']).convert('RGBA')
        else:
            background = Image.new('RGBA', (data['bg_width'], data['bg_height']), 'white')
        
        # Charger le premier plan
        if os.path.exists(data['foreground']):
            foreground = Image.open(data['foreground']).convert('RGBA')
        else:
            foreground = None
        
        # Convertir l'image personne en PIL
        person_pil = Image.fromarray(cv2.cvtColor(person_img, cv2.COLOR_BGR2RGB))
        
        # Créer une composition
        # 1. Créer la zone visible
        visible_zone = background.crop((
            data['visible_x'] + self.person_x.get(),
            data['visible_y'] + self.person_y.get(),
            data['visible_x'] + self.person_x.get() + data['visible_width'],
            data['visible_y'] + self.person_y.get() + data['visible_height']
        ))
        
        # 2. Redimensionner la personne à la taille de la zone visible
        person_resized = person_pil.resize((data['visible_width'], data['visible_height']), Image.Resampling.LANCZOS)
        
        # 3. Composer
        visible_zone.paste(person_resized, (0, 0), person_resized)
        
        # 4. Remettre la zone visible dans le fond
        background.paste(visible_zone, (
            data['visible_x'] + self.person_x.get(),
            data['visible_y'] + self.person_y.get()
        ))
        
        # 5. Ajouter le premier plan par-dessus
        if foreground:
            background.paste(foreground, (0, 0), foreground)
        
        return background.convert('RGB')
    
    def save_image_with_metadata(self, image, filepath):
        """Sauvegarde l'image avec les métadonnées"""
        # Créer les métadonnées EXIF
        exif_dict = {"0th": {}, "Exif": {}, "GPS": {}, "1st": {}, "thumbnail": None}
        
        # Ajouter l'email comme commentaire
        user_comment = piexif.helper.UserComment.dump(self.email.get(), encoding="unicode")
        exif_dict["Exif"][piexif.ExifIFD.UserComment] = user_comment
        
        # Ajouter d'autres informations
        exif_dict["0th"][piexif.ImageIFD.ImageDescription] = f"Photo de {self.photo_name.get()} - Set: {self.current_set.get()}"
        exif_dict["0th"][piexif.ImageIFD.DateTime] = datetime.now().strftime("%Y:%m:%d %H:%M:%S")
        exif_dict["0th"][piexif.ImageIFD.Software] = "Studio Photo Salon BD"
        
        # Convertir en bytes
        exif_bytes = piexif.dump(exif_dict)
        
        # Sauvegarder avec les métadonnées
        image.save(filepath, "JPEG", exif=exif_bytes, quality=95)

def main():
    root = tk.Tk()
    
    # Style
    style = ttk.Style()
    style.configure('Accent.TButton', font=('Arial', 12, 'bold'))
    
    app = GreenScreenApp(root)
    
    # Gestion fermeture
    def on_closing():
        if app.camera_running:
            app.stop_camera()
        root.destroy()
    
    root.protocol("WM_DELETE_WINDOW", on_closing)
    root.mainloop()

if __name__ == "__main__":
    main()