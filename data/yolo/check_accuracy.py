import os
import glob
import requests
import numpy as np
from PIL import Image
import onnxruntime as ort
import matplotlib.pyplot as plt
import matplotlib.patheffects as path_effects
import seaborn as sns
import os

# --- CONFIG ---
IMAGE_DIR = "wellington_pest_images"
TOTAL_IMAGES = 50
WELLINGTON_PLACE_ID = 7352 
PEST_SPECIES = [
    "Tradescantia fluminensis", "Clematis vitalba", "Asparagus scandens",
    "Passiflora tarminiana", "Solanum mauritianum", "Berberis darwinii",
    "Chrysanthemoides monilifera", "Ulex europaeus", "Cytisus scoparius",
    "Araujia hortorum"
]

def find_assets():
    models = os.path.join("best.onnx")
    if not models: raise FileNotFoundError("No .onnx file found.")
    labels = os.path.join("labels.txt")
    return models[0], (labels[0] if labels else None)

def get_model_config(session):
    # Fixed: Explicitly handle the input shape to avoid Pylance inference issues
    input_meta = session.get_inputs()[0]
    shape = input_meta.shape
    # Default to 224 if dimensions are dynamic (strings)
    h = shape[2] if isinstance(shape[2], int) else 224
    w = shape[3] if isinstance(shape[3], int) else 224
    return input_meta.name, (w, h)

def download_pests():
    if not os.path.exists(IMAGE_DIR): os.makedirs(IMAGE_DIR)
    data_log = []
    per_species = TOTAL_IMAGES // len(PEST_SPECIES)
    print("🌿 Gathering Wellington botanical samples...")
    for species in PEST_SPECIES:
        try:
            url = "https://api.inaturalist.org/v1/observations"
            params = {"taxon_name": species, "place_id": WELLINGTON_PLACE_ID, "per_page": per_species, "photos": "true"}
            res = requests.get(url, params=params).json()
            for obs in res.get('results', []):
                img_url = obs['photos'][0]['url'].replace('square', 'medium')
                path = os.path.join(IMAGE_DIR, f"{species.replace(' ', '_')}_{obs['id']}.jpg")
                if not os.path.exists(path):
                    with open(path, 'wb') as f: f.write(requests.get(img_url).content)
                data_log.append({"path": path, "species": species})
        except: continue
    return data_log

def create_watercolour_graph(results_dict, metric_name):
    print("🎨 Painting botanical chart...")
    species_names = list(results_dict.keys())
    # Ensure we don't divide by zero if a species failed to download
    values = [np.mean(results_dict[s]) if results_dict[s] else 0.0 for s in species_names]
    
    plt.figure(figsize=(12, 8), facecolor='#FCF9F2')
    ax = plt.gca()
    ax.set_facecolor('#FCF9F2')
    colors = sns.color_palette("Greens_d", len(species_names))
    
    for i, (name, val) in enumerate(zip(species_names, values)):
        for layer in range(5):
            jitter = np.random.uniform(-0.02, 0.02)
            plt.barh(i + jitter, val, color=colors[i], alpha=0.15, height=0.6)
        plt.barh(i, val, color=colors[i], alpha=0.6, height=0.5, edgecolor=colors[i], linestyle='--')
        txt = plt.text(val + 0.01, i, f"{val:.1%}", va='center', fontfamily='serif', fontweight='bold')
        txt.set_path_effects([path_effects.withStroke(linewidth=3, foreground="#FCF9F2")])

    for _ in range(40):
        plt.scatter(np.random.uniform(0, 1), np.random.uniform(-1, len(species_names)), 
                    s=np.random.randint(5, 40), color='#4F7942', alpha=0.05)

    plt.yticks(range(len(species_names)), [s.replace('_', ' ') for s in species_names], fontfamily='serif')
    plt.title(f"Wellington Pest Analysis Report\n{metric_name}", fontsize=16, fontfamily='serif', pad=20)
    plt.xlim(0, 1.1)
    sns.despine()
    plt.tight_layout()
    plt.savefig("accuracy_report.png", dpi=300)
    plt.show()

def main():
    # 1. Initialize variables to prevent "possibly unbound" errors
    metric = "Detection Confidence" 
    class_map = {}
    results = {s: [] for s in PEST_SPECIES}
    
    # 2. Setup Assets
    model_path, label_path = find_assets()
    session = ort.InferenceSession(model_path)
    input_name, target_size = get_model_config(session)
    
    if label_path:
        metric = "Classification Accuracy"
        with open(label_path, 'r') as f:
            class_map = {i: line.strip().lower() for i, line in enumerate(f.readlines())}

    # 3. Process Images
    image_data = download_pests()
    print(f"🔍 Testing {len(image_data)} images against {model_path}...")

    for item in image_data:
        try:
            img = Image.open(item['path']).convert('RGB').resize(target_size)
            img_array = np.array(img).astype('float32') / 255.0
            tensor = np.transpose(img_array, (2, 0, 1))[np.newaxis, :]
            
            # --- FIXED: Indexing Issue ---
            # session.run returns a list. We take the first output.
            raw_output = session.run(None, {input_name: tensor})
            output_tensor = np.array(raw_output[0]) # Convert to numpy to avoid SparseTensor error
            
            # Squeeze to remove batch dim if necessary
            preds = np.squeeze(output_tensor)
            if preds.ndim > 1: # Handle YOLO [classes, boxes] vs standard [classes]
                preds = preds.flatten()

            # --- FIXED: ArgumentType / intp Issue ---
            # argmax returns a numpy intp; dictionary .get() requires a standard Python int
            pred_idx_raw = np.argmax(preds)
            pred_idx = int(pred_idx_raw) 
            
            # Softmax for confidence
            conf = np.exp(preds[pred_idx]) / np.sum(np.exp(preds))

            if class_map:
                # Compare label text to species folder name
                predicted_label = class_map.get(pred_idx, "unknown")
                is_correct = 1.0 if predicted_label in item['species'].lower() else 0.0
                results[item['species']].append(is_correct)
            else:
                results[item['species']].append(float(conf))
                
        except Exception as e:
            print(f"Skipping {item['path']}: {e}")

    # 4. Final Painting
    create_watercolour_graph(results, metric)

if __name__ == "__main__":
    main()