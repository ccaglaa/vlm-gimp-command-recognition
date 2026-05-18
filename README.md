# PAI2D — Assistant GIMP par VLM
Sorbonne Université 2025-2026

Observe le canvas GIMP toutes les 10s. Quand il détecte un changement, il suggère la commande GIMP optimale qui aurait produit le même résultat en un clic.

---

## Prérequis

- GIMP 3.2.x
- Python 3.9+ (pour le serveur)
- 8 Go RAM minimum
- GPU Apple Silicon (MPS) ou NVIDIA (CUDA) recommandé (fonctionne aussi sur CPU mais lent)

---

## Installation

### 1. Dépendances du serveur

```bash
python3 -m venv venv
source venv/bin/activate
pip install -r requirements.txt
```

### 2. Plugin GIMP

Le dossier et le fichier doivent avoir le même nom.

**macOS**
```bash
cp -r Plugin3 ~/Library/Application\ Support/GIMP/3.2/plug-ins/
chmod +x ~/Library/Application\ Support/GIMP/3.2/plug-ins/Plugin3/Plugin3.py
```

**Linux**
```bash
cp -r Plugin3 ~/.config/GIMP/3.2/plug-ins/
chmod +x ~/.config/GIMP/3.2/plug-ins/Plugin3/Plugin3.py
```

Redémarrer GIMP après l'installation.

### 3. Modèle

Télécharger le dossier `qwen2vl-gimp-lora` depuis le lien partagé et le placer où vous voulez sur votre machine.

---

## Lancement

### Étape 1: Démarrer le serveur

```bash
source venv/bin/activate
MODEL_PATH=/chemin/vers/qwen2vl-gimp-lora uvicorn server:app --host 0.0.0.0 --port 8000
```

Attendre : `Modèle prêt` et `Application startup complete.`

### Étape 2: Démarrer le plugin dans GIMP

1. Ouvrir GIMP avec une image
2. **Filtres → Plugin3 → Démarrer la surveillance**
3. Le panneau flottant "Assistant GIMP" apparaît

### Étape 3: Utiliser

Appliquer n'importe quel filtre ou transformation dans GIMP. Le système détecte le changement, envoie les images au serveur, et affiche une suggestion dans le panneau.

---

## Paramètres

Dans `Plugin3.py` :
| Variable | Valeur | Description |
|----------|--------|-------------|
| `DELTA_THRESHOLD` | `1.5` | Différence pixel minimale pour déclencher l'inférence (1.5 = détecte les yeux rouges) |
| `CAPTURE_INTERVAL` | `10` | Secondes entre chaque capture |
| `COOLDOWN_SECONDS` | `60` | Délai minimum entre deux suggestions identiques |

Dans `server.py` :
| Variable | Valeur | Description |
|----------|--------|-------------|
| `CONFIDENCE_GATE` | `0.0` | Seuil de confiance minimum (0.0 = tout afficher, 0.20 = production) |

---

## Commandes reconnues (13 classes)

`brightness_contrast` · `colorize` · `desaturate` · `edge_detect` · `flip` · `gaussian_blur` · `hue_saturation` · `invert` · `posterize` · `red_eye_removal` · `rotation` · `sharpen` · `threshold`

---
