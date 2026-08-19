import os
import requests
import threading
import time
from pathlib import Path
from concurrent.futures import ThreadPoolExecutor
from ddgs import DDGS
from tqdm import tqdm

# --- CONFIGURATION ---
ROOT_FOLDER = Path("Dataset")
TARGETS = {"train": 600, "val": 150}
MAX_THREADS = 50 

# Latin names are the "secret key" to finding 600+ images for weeds
SCIENTIFIC_NAMES = {
    "annual_poa": "Poa annua",
    "black_nightshade": "Solanum nigrum",
    "blackberry": "Rubus fruticosus",
    "bracken": "Pteridium aquilinum",
    "broad_leaved_dock": "Rumex obtusifolius",
    "broom": "Cytisus scoparius",
    "californian_thistle": "Cirsium arvense",
    "cape_weed": "Arctotheca calendula",
    "catsear": "Hypochaeris radicata",
    "chickweed": "Stellaria media",
    "cleavers": "Galium aparine",
    "couch": "Cynodon dactylon",
    "creeping_buttercup": "Ranunculus repens",
    "creeping_oxalis": "Oxalis corniculata",
    "creeping_speedwell": "Veronica filiformis",
    "daisy": "Bellis perennis",
    "dandelion": "Taraxacum officinale",
    "gorse": "Ulex europaeus",
    "hawkbit": "Leontodon saxatilis",
    "hawksbeard": "Crepis capillaris",
    "manuka": "Leptospermum scoparium",
    "old_mans_beard": "Clematis vitalba",
    "onehunga_weed": "Soliva sessilis",
    "paspalum": "Paspalum dilatatum",
    "ragwort": "Jacobaea vulgaris",
    "sheeps_sorrel": "Rumex acetosella",
    "white_clover": "Trifolium repens"
}

class RefillEngine:
    def __init__(self):
        self.session = requests.Session()
        self.session.headers.update({"User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36"})

    def fetch_urls(self, plant_norm, count_needed):
        urls = set()
        # Use Latin name if we have it, otherwise clean common name
        search_query = SCIENTIFIC_NAMES.get(plant_norm, plant_norm.replace("_", " "))
        
        # 1. iNaturalist (High quality/Scientific)
        try:
            r = self.session.get(f"https://api.inaturalist.org/v1/observations?q={search_query}&quality_grade=research&per_page=200", timeout=5).json()
            for obs in r.get('results', []):
                for p in obs.get('photos', []):
                    urls.add(p.get('url', '').replace('square', 'large'))
        except: pass

        # 2. GBIF (Museum/Academic)
        if len(urls) < count_needed:
            try:
                r = self.session.get(f"https://api.gbif.org/v1/occurrence/search?q={search_query}&mediaType=StillImage&limit=200", timeout=5).json()
                for rec in r.get('results', []):
                    for m in rec.get('media', []):
                        urls.add(m.get('identifier'))
            except: pass

        # 3. DuckDuckGo (Bulk)
        if len(urls) < count_needed:
            try:
                with DDGS() as ddgs:
                    # We search for "plant" specifically to avoid non-botanical results
                    res = list(ddgs.images(f"{search_query} plant", max_results=count_needed + 50))
                    for x in res: urls.add(x['image'])
            except: pass
        
        return list(urls)

    def download_img(self, url, dest_path, pbar):
        try:
            r = self.session.get(url, timeout=5)
            if r.status_code == 200:
                ext = url.split('.')[-1].split('?')[0].lower()
                if ext not in ['jpg', 'jpeg', 'png', 'webp']: ext = 'jpg'
                with open(dest_path.with_suffix(f".{ext}"), 'wb') as f:
                    f.write(r.content)
        except: pass
        pbar.update(1)

    def run(self):
        print("🚀 Refill Engine Engaged: Targeting missing images...")
        
        # Get list of folders in train/val
        for split, target in TARGETS.items():
            split_dir = ROOT_FOLDER / split
            if not split_dir.exists(): continue

            folders = [f for f in split_dir.iterdir() if f.is_dir()]
            
            for folder in folders:
                existing_files = list(folder.glob("*.*"))
                current_count = len(existing_files)
                
                if current_count >= target:
                    continue

                needed = target - current_count
                plant_name = folder.name
                print(f"\n📦 {split}/{plant_name}: {current_count}/{target} (Refilling {needed})")
                
                urls = self.fetch_urls(plant_name, needed)
                
                if not urls:
                    print(f"  ⚠️ Could not find more URLs for {plant_name}")
                    continue

                # Download into the folder
                with tqdm(total=needed, desc=f"Refilling {plant_name[:12]}", unit="img") as pbar:
                    with ThreadPoolExecutor(max_workers=MAX_THREADS) as exec:
                        for i in range(needed):
                            if i < len(urls):
                                # Correct numbering: annual_po_0585, 0586, etc.
                                idx = current_count + i + 1
                                fname = f"{plant_name}_{str(idx).zfill(4)}"
                                exec.submit(self.download_img, urls[i], folder / fname, pbar)

                time.sleep(2) # Prevent API bans between plants

if __name__ == "__main__":
    RefillEngine().run()
