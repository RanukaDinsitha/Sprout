import os
import sys
import glob
import time
import requests
import numpy as np
from PIL import Image
import onnxruntime as ort
import matplotlib.pyplot as plt
import matplotlib.patheffects as path_effects
from matplotlib.patches import FancyBboxPatch
import matplotlib.font_manager as fm
import seaborn as sns
from concurrent.futures import ThreadPoolExecutor, as_completed
from tqdm import tqdm

# --- CONFIG ---
IMAGE_DIR = "wellington_pest_images"
TOTAL_IMAGES = 50
WELLINGTON_PLACE_ID = 6867  # Wellington Region, NZ (was 7352 — invalid/near-empty place, caused near-zero results)
MAX_WORKERS = 20  # parallel download threads
PEST_SPECIES = [
    "Tradescantia fluminensis", "Clematis vitalba", "Asparagus scandens",
    "Passiflora tarminiana", "Solanum mauritianum", "Berberis darwinii",
    "Chrysanthemoides monilifera", "Ulex europaeus", "Cytisus scoparius",
    "Araujia hortorum"
]


def find_assets():
    models = glob.glob("*.onnx") + glob.glob(os.path.join("**", "*.onnx"), recursive=True)
    if not models:
        raise FileNotFoundError("No .onnx file found.")
    labels = glob.glob("*.txt") + glob.glob(os.path.join("**", "labels.txt"), recursive=True)
    return models[0], (labels[0] if labels else None)


def get_model_config(session):
    input_meta = session.get_inputs()[0]
    shape = input_meta.shape
    h = shape[2] if isinstance(shape[2], int) else 224
    w = shape[3] if isinstance(shape[3], int) else 224
    return input_meta.name, (w, h)


def _fetch_observation_urls(species, per_species, place_id=WELLINGTON_PLACE_ID):
    """Hit the iNaturalist API for one species and return (url, path, species) tuples.
    place_id=None searches nationwide (NZ), used as a fallback when the regional
    search comes up short for a species."""
    tasks = []
    url = "https://api.inaturalist.org/v1/observations"
    params = {
        "taxon_name": species,
        "per_page": per_species,
        "photos": "true",
    }
    if place_id is not None:
        params["place_id"] = place_id
    try:
        res = requests.get(url, params=params, timeout=10).json()
        for obs in res.get("results", []):
            photos = obs.get("photos")
            if not photos:
                continue
            img_url = photos[0]["url"].replace("square", "medium")
            path = os.path.join(IMAGE_DIR, f"{species.replace(' ', '_')}_{obs['id']}.jpg")
            tasks.append((img_url, path, species))
    except Exception:
        pass
    return tasks


def _download_one(task):
    img_url, path, species = task
    if not os.path.exists(path):
        try:
            r = requests.get(img_url, timeout=10)
            r.raise_for_status()
            with open(path, "wb") as f:
                f.write(r.content)
        except Exception:
            return None
    return {"path": path, "species": species}


def download_pests():
    if not os.path.exists(IMAGE_DIR):
        os.makedirs(IMAGE_DIR)

    per_species = max(1, TOTAL_IMAGES // len(PEST_SPECIES))
    per_species_fetch = per_species + 2  # over-fetch a little in case some obs lack photos

    # 1. Gather candidate image URLs (metadata lookups) in parallel across species.
    #    Regional (Wellington) search first; if a species comes up short, backfill
    #    with a nationwide search so we still land close to TOTAL_IMAGES.
    print("Looking up observations...")
    all_tasks = []
    with ThreadPoolExecutor(max_workers=len(PEST_SPECIES)) as executor:
        futures = {executor.submit(_fetch_observation_urls, s, per_species_fetch): s for s in PEST_SPECIES}
        shortfalls = []
        for f in as_completed(futures):
            species = futures[f]
            tasks = f.result()
            if len(tasks) < per_species:
                shortfalls.append(species)
            all_tasks.extend(tasks)

    if shortfalls:
        with ThreadPoolExecutor(max_workers=max(1, len(shortfalls))) as executor:
            futures = [executor.submit(_fetch_observation_urls, s, per_species_fetch, None) for s in shortfalls]
            for f in as_completed(futures):
                all_tasks.extend(f.result())

    # De-dupe by path, then cap at TOTAL_IMAGES
    seen = set()
    deduped = []
    for t in all_tasks:
        if t[1] not in seen:
            seen.add(t[1])
            deduped.append(t)
    all_tasks = deduped[:TOTAL_IMAGES]

    if not all_tasks:
        print("No observations found — check WELLINGTON_PLACE_ID and species names.")
        return []

    # 2. Download the actual image bytes in parallel with a progress bar
    data_log = []
    start = time.time()
    with ThreadPoolExecutor(max_workers=MAX_WORKERS) as executor:
        futures = [executor.submit(_download_one, t) for t in all_tasks]
        for f in tqdm(as_completed(futures), total=len(futures),
                      desc="Downloading images", unit="img", ncols=80, colour="green"):
            result = f.result()
            if result:
                data_log.append(result)
    elapsed = time.time() - start
    print(f"Downloaded {len(data_log)}/{len(all_tasks)} images in {elapsed:.1f}s")
    return data_log


def create_watercolour_graph(results_dict, metric_name):
    print("Rendering chart...")

    # Sort species by score, descending, so the chart tells a story top-to-bottom
    species_names = list(results_dict.keys())
    values = [np.mean(results_dict[s]) if results_dict[s] else 0.0 for s in species_names]
    order = np.argsort(values)  # ascending, so best ends up at top of barh
    species_names = [species_names[i] for i in order]
    values = [values[i] for i in order]
    n = len(species_names)

    serif = "serif"
    try:
        if any("Georgia" in f.name for f in fm.fontManager.ttflist):
            serif = "Georgia"
    except Exception:
        pass

    fig = plt.figure(figsize=(12, 8.5), facecolor="#FBF7EE")
    ax = plt.gca()
    ax.set_facecolor("#FBF7EE")

    # Soft radial-ish vignette using scattered dots (kept from original watercolour idea)
    rng = np.random.default_rng(7)
    for _ in range(90):
        ax.scatter(rng.uniform(0, 1.05), rng.uniform(-1, n),
                   s=rng.integers(4, 45), color="#4F7942", alpha=0.04, zorder=0)

    palette = sns.color_palette("Greens_d", n)[::-1]

    for i, (name, val) in enumerate(zip(species_names, values)):
        color = palette[i]
        # watercolour "bleed" layers
        for _ in range(6):
            jitter = rng.uniform(-0.015, 0.015)
            ax.barh(i + jitter, val, color=color, alpha=0.12, height=0.62, zorder=1)
        # crisp bar on top
        ax.barh(i, val, color=color, alpha=0.75, height=0.5,
                 edgecolor=color, linewidth=1.2, zorder=2)
        # value label
        txt = ax.text(val + 0.015, i, f"{val:.0%}", va="center", ha="left",
                       fontfamily=serif, fontweight="bold", fontsize=11, color="#2F4F2F", zorder=3)
        txt.set_path_effects([path_effects.withStroke(linewidth=3, foreground="#FBF7EE")])

    ax.set_yticks(range(n))
    ax.set_yticklabels([s.replace("_", " ") for s in species_names], fontfamily=serif, fontsize=11.5)
    ax.set_xlim(0, 1.12)
    ax.set_xticks([0, 0.25, 0.5, 0.75, 1.0])
    ax.set_xticklabels(["0%", "25%", "50%", "75%", "100%"], fontfamily=serif, fontsize=10, color="#5c5c5c")
    ax.xaxis.grid(True, color="#4F7942", alpha=0.12, linewidth=0.8, zorder=0)
    ax.set_axisbelow(True)

    total_images = sum(len(v) for v in results_dict.values())
    ax.set_title("Wellington Pest Detection Report", fontsize=20, fontfamily=serif,
                 fontweight="bold", color="#2F4F2F", pad=34)
    ax.text(0.5, 1.045, f"{metric_name}  ·  {total_images} images  ·  {n} species",
            transform=ax.transAxes, ha="center", fontsize=11.5, fontfamily=serif,
            color="#6b6b6b", style="italic")

    sns.despine(left=True, bottom=True)
    ax.tick_params(left=False, bottom=False)

    plt.tight_layout(rect=(0, 0, 1, 0.96))
    out_path = "accuracy_report.png"
    plt.savefig(out_path, dpi=300, facecolor=fig.get_facecolor())
    plt.close(fig)
    print(f"Chart saved to {out_path}")


def main():
    metric = "Detection Confidence"
    class_map = {}
    results = {s: [] for s in PEST_SPECIES}

    model_path, label_path = find_assets()
    session = ort.InferenceSession(model_path)
    input_name, target_size = get_model_config(session)

    if label_path:
        metric = "Classification Accuracy"
        with open(label_path, "r") as f:
            class_map = {i: line.strip().lower() for i, line in enumerate(f.readlines())}

    # 1. Download (fast, parallel, with progress bar)
    image_data = download_pests()

    # 2. Run inference
    print(f"Testing {len(image_data)} images against {model_path}...")
    for item in image_data:
        try:
            img = Image.open(item["path"]).convert("RGB").resize(target_size)
            img_array = np.array(img).astype("float32") / 255.0
            tensor = np.transpose(img_array, (2, 0, 1))[np.newaxis, :]

            raw_output = session.run(None, {input_name: tensor})
            output_tensor = np.array(raw_output[0])
            preds = np.squeeze(output_tensor)
            if preds.ndim > 1:
                preds = preds.flatten()

            pred_idx = int(np.argmax(preds))
            conf = np.exp(preds[pred_idx]) / np.sum(np.exp(preds))

            if class_map:
                predicted_label = class_map.get(pred_idx, "unknown")
                is_correct = 1.0 if predicted_label in item["species"].lower() else 0.0
                results[item["species"]].append(is_correct)
            else:
                results[item["species"]].append(float(conf))

        except Exception as e:
            print(f"Skipping {item['path']}: {e}")

    # 3. Graph
    create_watercolour_graph(results, metric)

    # 4. Exit cleanly
    print("Done.")
    sys.exit(0)


if __name__ == "__main__":
    main()