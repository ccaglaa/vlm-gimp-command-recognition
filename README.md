# PAI2D — Assistant GIMP par VLM
Sorbonne Université — Master AI2D 2025-2026

Projet encadré par **Julien Gori**, **Olivier Schwander** et **Gilles Bailly**.
Réalisé par **Çagla Koprulu**, **Riadh Ouazib**, **Andy Ngo** et **Louiza Chenaoui**.

L'idée : les utilisateurs de logiciels complexes n'exploitent qu'une infime partie des commandes disponibles. Ce système observe le canvas GIMP avant et après une action, et suggère la commande native qui aurait produit le même résultat en un clic.

---

```markdown
[![Démo PAI2D](https://img.youtube.com/vi/y76A7swac5c/0.jpg)](https://youtu.be/y76A7swac5c)
```

## Structure du dépôt

- **`plugin.py`** — Plugin GIMP (Python-Fu), capture le canvas et envoie les composites au serveur
- **`server.py`** — Serveur d'inférence FastAPI, charge le modèle et retourne les prédictions
- **`requirements.txt`** — Dépendances Python du serveur
- **`entrainement/`** — Notebooks Kaggle pour le fine-tuning QLoRA (Qwen2-VL-2B-Instruct)
- **`generation_dataset/`** — Scripts de génération du dataset (2 versions) via l'API Python-Fu de GIMP

---

## Modèles (HuggingFace)

| Lien | Classes | Format |
|------|---------|--------|
| [ccaglaa/qwen2vl-gimp-lora](https://huggingface.co/ccaglaa/qwen2vl-gimp-lora) | 20 | double panneau |
| [ccaglaa/qwen2vl-2b-gimp-ai2d-v3](https://huggingface.co/ccaglaa/qwen2vl-2b-gimp-ai2d-v3/tree/main) | 13 | triptyque |
| [Riadhouazib/qwen2vl-gimp-lora-40cmd](https://huggingface.co/Riadhouazib/qwen2vl-gimp-lora-40cmd/tree/main/modele) | 40 | triptyque |

## Datasets (Kaggle)

| Lien | Classes |
|------|---------|
| [pai2d-train-dataset-v4](https://www.kaggle.com/datasets/ccaglaa/pai2d-train-dataset-v4) | 40 |
| [ai2d-v3-dataset](https://www.kaggle.com/datasets/ccaglaa/ai2d-v3-dataset) | 13 |

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

Le dossier et le fichier doivent avoir le même nom — contrainte de GIMP 3.x.

**macOS**
```bash
mkdir -p ~/Library/Application\ Support/GIMP/3.2/plug-ins/Plugin3
cp plugin.py ~/Library/Application\ Support/GIMP/3.2/plug-ins/Plugin3/Plugin3.py
chmod +x ~/Library/Application\ Support/GIMP/3.2/plug-ins/Plugin3/Plugin3.py
```

**Linux**
```bash
mkdir -p ~/.config/GIMP/3.2/plug-ins/Plugin3
cp plugin.py ~/.config/GIMP/3.2/plug-ins/Plugin3/Plugin3.py
chmod +x ~/.config/GIMP/3.2/plug-ins/Plugin3/Plugin3.py
```

Redémarrer GIMP après l'installation.

### 3. Modèle

Télécharger depuis HuggingFace (voir tableau ci-dessus) ou utiliser directement l'identifiant dans la commande de lancement.

---

## Lancement

### Étape 1 : Démarrer le serveur

```bash
source venv/bin/activate

# Depuis HuggingFace
MODEL_PATH=ccaglaa/qwen2vl-2b-gimp-ai2d-v3 uvicorn server:app --host 0.0.0.0 --port 8000

# Depuis un dossier local
MODEL_PATH=/chemin/vers/qwen2vl-gimp-lora uvicorn server:app --host 0.0.0.0 --port 8000
```

Attendre : `Modèle prêt` et `Application startup complete.`

### Étape 2 : Démarrer le plugin dans GIMP

1. Ouvrir GIMP avec une image
2. **Filtres → Plugin3 → Démarrer la surveillance**
3. Le panneau flottant "Assistant GIMP" apparaît

### Étape 3 : Utiliser

Appliquer n'importe quel filtre ou transformation dans GIMP. Le système détecte le changement, envoie les images au serveur, et affiche une suggestion dans le panneau.

---

## Paramètres

Dans `plugin.py` :
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
