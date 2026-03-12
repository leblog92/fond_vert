import cv2
import tkinter as tk
from tkinter import ttk, messagebox

def test_cameras():
    """Teste les différentes caméras disponibles"""
    working_cameras = []
    
    for i in range(5):  # Tester les 5 premiers indices
        cap = cv2.VideoCapture(i)
        if cap.isOpened():
            ret, frame = cap.read()
            if ret:
                working_cameras.append(i)
            cap.release()
    
    return working_cameras

def main():
    print("Recherche des caméras disponibles...")
    cameras = test_cameras()
    
    if cameras:
        print(f"Caméras trouvées aux indices: {cameras}")
        print("Si Iriun est installé, il devrait apparaître dans cette liste.")
        print("Vous pouvez modifier l'index dans config.json")
    else:
        print("Aucune caméra trouvée!")
        print("Vérifiez que Iriun est bien installé et que la tablette est connectée.")

if __name__ == "__main__":
    main()