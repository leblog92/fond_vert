# Studio Photo Fond Vert — Salon BD

Application Python de montage photo en temps réel pour fond vert, développée pour le **Salon BD de Rueil-Malmaison 2026**. Elle permet de composer automatiquement une photo de visiteur sur l'un des quatre décors illustrés de l'événement, avec premier plan et métadonnées personnalisées.

---

## Aperçu

```
┌─────────────────────────────────────────────────────────────────┐
│  Caméra + détourage  │    Aperçu montage en direct    │  Sets   │
│  ──────────────────  │  ─────────────────────────────  │  X/Y/Z  │
│  Paramètres chroma   │                                 │  Nom    │
│                      │                                 │  Email  │
│                      │                                 │  📷     │
└─────────────────────────────────────────────────────────────────┘
```

---

## Fonctionnalités

- **Détourage fond vert en temps réel** via masque HSV avec réglages fins (teinte min/max, saturation, luminance, érosion, dilatation, lissage)
- **4 sets de décors** indépendants avec fond, premier plan et zones de positionnement configurés précisément
- **Aperçu en direct** du montage composé à 5 fps (fichiers UI 600px pour la fluidité)
- **Composition finale** en pleine résolution (2000px) avec les fichiers originaux
- **Correcteurs de position** X, Y et Z (zoom) avec plage ±500px et zoom 50–200%
- **Barre de progression** au démarrage de la caméra (~25s pour la Logitech C270)
- **Sauvegarde JPEG** qualité 85 avec métadonnées EXIF (nom, email, date, set)
- **Fichier `.txt` associé** pour chaque prise de vue (nom, email, set, date)
- Interface en **français**

---

## Structure du projet

```
fond_vert/
├── main.py               # Interface graphique PyQt5
├── image_processor.py    # Détourage, composition, sauvegarde
├── camera_manager.py     # Thread caméra, scanner
├── config.py             # Paramètres des 4 sets (résolutions, zones)
├── requirements.txt
├── install.bat           # Installation des dépendances (Windows)
├── run.bat               # Lancement
└── assets/
    ├── fond1.jpg         # Fond pleine résolution set 1  (2000×1688)
    ├── pp1.png           # Premier plan set 1            (2000×1688)
    ├── UI_fond1.jpg      # Fond UI set 1                 (600×506)
    ├── UI_pp1.png        # Premier plan UI set 1         (600×506)
    ├── fond2.jpg / pp2.png / UI_fond2.jpg / UI_pp2.png
    ├── fond3.jpg / pp3.png / UI_fond3.jpg / UI_pp3.png
    └── fond4.jpg / pp4.png / UI_fond4.jpg / UI_pp4.png
```

---

## Configuration des sets

| Set | Fond (px)   | Zone caméra (px) | Position zone |
|-----|-------------|------------------|---------------|
| 1   | 2000 × 1688 | 1061 × 597       | X=−80, Y=959  |
| 2   | 2000 × 1414 | 2286 × 1286      | X=−137, Y=68  |
| 3   | 2000 × 2632 | 1267 × 711       | X=942, Y=1713 |
| 4   | 2000 × 2633 | 1890 × 1063      | X=74, Y=1253  |

Chaque set dispose de deux jeux de fichiers :
- **Pleine résolution** (`fond*.jpg` / `pp*.png`) — utilisés uniquement pour le montage final sauvegardé
- **Fichiers UI** (`UI_fond*.jpg` / `UI_pp*.png`, 600px) — chargés une seule fois en cache pour la prévisualisation temps réel

---

## Prérequis

- Windows 10 / 11
- Python 3.13+
- Caméra USB (testé : Logitech C270 HD, 1280×720)

---

## Installation

```bat
install.bat
```

Ou manuellement :

```bash
pip install opencv-python==4.10.0.84 Pillow==11.0.0 numpy==2.0.2 PyQt5==5.15.11 pyqt5-plugins==5.15.11.1.3 piexif==1.1.3
```

---

## Lancement

```bat
run.bat
```

Ou :

```bash
python main.py
```

---

## Utilisation

1. **Scanner** les caméras disponibles puis **Démarrer** — une barre de progression indique l'initialisation (~25s)
2. Sélectionner un **set** dans le menu déroulant
3. Ajuster les **paramètres de détourage** si nécessaire (teinte, saturation, lissage…)
4. Positionner la personne avec les **correcteurs X / Y / Z**
5. Saisir le **nom** et l'**adresse email** de la personne
6. Cliquer sur **PRENDRE LA VUE** — l'image est sauvegardée dans `%USERPROFILE%\Pictures\salonBD\`

---

## Fichiers sauvegardés

Pour chaque prise de vue, deux fichiers sont créés :

```
salonBD_Jean Dupont_20260327_143022_set1.jpg   # montage JPEG qualité 85
salonBD_Jean Dupont_20260327_143022_set1.txt   # nom, email, set, date
```

Les métadonnées EXIF embarquées dans le JPEG incluent le nom (Artist, XPAuthor), l'email (UserComment, XPComment), les mots-clés et la date de prise de vue — visibles dans les propriétés de fichier Windows.

---

## Architecture technique

### `image_processor.py`

- `extract_person()` — masque HSV → BGRA natif OpenCV (pas de conversion intermédiaire)
- `_blend_onto()` — composition alpha avec **clipping partiel** : gère les zones qui dépassent les bords du canvas (nécessaire pour le set 2 dont la zone caméra dépasse la largeur du fond)
- `_composite()` — composition générique fond + personne + premier plan, entièrement en BGR/BGRA natif OpenCV
- `create_preview()` — utilise les fichiers UI 600px déjà en cache, met à l'échelle les décalages X/Y par `UI_SCALE=0.3`
- `composite_image()` — même logique, fichiers pleine résolution

### `camera_manager.py`

- `CameraThread` — thread Qt dédié, `cap.release()` dans le thread lui-même, `stop()` non bloquant
- `CameraScanner` — scan des indices 0 à 9

### `main.py`

- Cache UI (`_ui_cache`) — chargement unique par set au premier accès
- `_safe_stop_thread()` — arrêt avec timeout 3s avant terminaison forcée
- `closeEvent()` — arrête timers et thread avant fermeture, sans passer par `stop_camera()` pour éviter les effets de bord sur les widgets

---

## Améliorations envisagées

- Persistance des paramètres de détourage et de position entre sessions (`settings.json`)
- Prévisualisation du masque alpha (mode noir/blanc pour le réglage chroma)
- Compte à rebours visuel avant prise de vue
- Historique des dernières prises (miniatures dans l'interface)
- Correcteur de rotation de la personne
- Validation de l'email avant sauvegarde
- Mode opérateur simplifié (interface réduite sans paramètres techniques)

---

## Licence

Projet développé pour le Salon BD de Rueil-Malmaison. Usage interne.
