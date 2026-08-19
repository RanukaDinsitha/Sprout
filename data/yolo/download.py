import os
import requests
import threading
import time
from pathlib import Path
from concurrent.futures import ThreadPoolExecutor
from ddgs import DDGS
from tqdm import tqdm
import pyjokes

# --- CONFIGURATION ---
ROOT_FOLDER = Path("PlantDataset")
TRAIN_COUNT = 600
VAL_COUNT = 150
MAX_THREADS = 80 

PLANTS = [
    "Annual poa", "Black nightshade", "Blackberry", "Bracken", "Broad-leaved dock", 
    "Broad-leaved fleabane", "Broad-leaved plantain", "Broom", "Californian thistle", 
    "Cape weed", "Catsear", "Chickweed", "Cleavers", "Clustered dock", "Couch", 
    "Creeping buttercup", "Creeping oxalis", "Creeping speedwell", "Daisy", 
    "Dandelion", "Fiddle dock", "Field speedwell", "Galinsoga", "Giant buttercup", 
    "Gorse", "Great bindweed", "Groundsel", "Hairy buttercup", "Hawkbit", 
    "Hawksbeard", "Hedge mustard", "Hemlock", "Hydrocotyle", "Ivy", "Mallow", 
    "Manuka", "Mouse-ear hawkweed", "Musky storksbill", "Narrow-leaved plantain", 
    "Nettle", "Nodding thistle", "Old man's beard", "Onehunga weed", "Oxeye daisy", 
    "Parsley dropwort", "Parsley piert", "Paspalum", "Pennyroyal", "Pink shamrock", 
    "Ragwort", "Red dead-nettle", "Redroot", "Scarlet pimpernel", "Scotch thistle", 
    "Scrambling fumitory", "Scrambling speedwell", "Selfheal", "Sheep's sorrel", 
    "Shepherd's purse", "Sow thistle", "Spurrey", "Staggerweed", "Stinking mayweed", 
    "Suckling clover", "Sweet brier", "Tauhinu", "Tradescantia", "Turf speedwell", 
    "Twin cress", "Water pepper", "White clover", "Wild radish", "Wild turnip", 
    "Willow weed", "Winged thistle", "Wireweed", "Yarrow"
]

class PlantCrawler:
    def __init__(self):
        self.session = requests.Session()
        self.session.headers.update({"User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36"})
        self.lock = threading.Lock()

    def trim_excess(self, folder_path, limit):
        """Deletes files if they exceed the limit to keep dataset perfectly balanced."""
        if not folder_path.exists(): return 0
        # Sort files alphabetically to ensure we keep the lowest numbered ones
        files = sorted([f for f in folder_path.glob("*.*") if f.is_file()])
        if len(files) > limit:
            to_delete = files[limit:]
            for f in to_delete:
                try: f.unlink()
                except: pass
            return limit
        return len(files)

    def fetch_urls(self, plant_name, quota):
        """Aggressive URL gathering from 3 sources."""
        urls = set()
        
        # 1. iNaturalist
        try:
            r = self.session.get(f"https://api.inaturalist.org/v1/observations?q={plant_name}&quality_grade=research&per_page=200", timeout=5)
            if r.status_code == 200:
                for obs in r.json().get('results', []):
                    for p in obs.get('photos', []):
                        u = p.get('url', '').replace('square', 'large')
                        if u: urls.add(u)
        except: pass

        # 2. GBIF
        if len(urls) < quota:
            try:
                r = self.session.get(f"https://api.gbif.org/v1/occurrence/search?q={plant_name}&mediaType=StillImage&limit=200", timeout=5)
                if r.status_code == 200:
                    for rec in r.json().get('results', []):
                        for m in rec.get('media', []):
                            u = m.get('identifier')
                            if u: urls.add(u)
            except: pass

        # 3. DuckDuckGo (Multiple Queries)
        if len(urls) < quota:
            for q in [f"{plant_name} plant", f"{plant_name} weed botanical"]:
                try:
                    with DDGS() as ddgs:
                        res = list(ddgs.images(q, max_results=quota))
                        for x in res: urls.add(x['image'])
                    if len(urls) >= quota: break
                    time.sleep(1)
                except: continue
        
        return list(urls)

    def download_file(self, url, dest_path_no_ext, pbar):
        try:
            r = self.session.get(url, timeout=5)
            if r.status_code == 200:
                ext = url.split('.')[-1].split('?')[0].lower()
                if ext not in ['jpg', 'jpeg', 'png', 'webp']: ext = 'jpg'
                with open(dest_path_no_ext.with_suffix(f".{ext}"), 'wb') as f:
                    f.write(r.content)
        except: pass
        pbar.update(1)

    def run(self):
        print(f"🌿 Plantcrawl Engine: Targeted Clean-up & Download")
        
        for plant in PLANTS:
            clean_name = plant.replace(" ", "_").lower()
            train_dir = ROOT_FOLDER / "train" / plant
            val_dir = ROOT_FOLDER / "val" / plant
            train_dir.mkdir(parents=True, exist_ok=True)
            val_dir.mkdir(parents=True, exist_ok=True)

            # --- TRIM PHASE ---
            count_t = self.trim_excess(train_dir, TRAIN_COUNT)
            count_v = self.trim_excess(val_dir, VAL_COUNT)
            
            needed_t = TRAIN_COUNT - count_t
            needed_v = VAL_COUNT - count_v

            if needed_t <= 0 and needed_v <= 0:
                print(f"✅ {plant}: Perfectly balanced (600/150).")
                continue

            # --- DOWNLOAD PHASE ---
            print(f"🔍 {plant}: Needs {needed_t} train, {needed_v} val. Searching...")
            print(pyjokes.get_joke())
            urls = self.fetch_urls(plant, (needed_t + needed_v) + 100)

            if not urls:
                print(f"⚠️ Search failed for {plant}!")
                continue

            t_urls = urls[:needed_t]
            v_urls = urls[needed_t : needed_t + needed_v]

            with tqdm(total=len(t_urls) + len(v_urls), desc=f"📂 {plant[:15]}", unit="img") as pbar:
                with ThreadPoolExecutor(max_workers=MAX_THREADS) as exec:
                    # Fill Train
                    for i, u in enumerate(t_urls):
                        fname = f"{clean_name}_{str(count_t + i + 1).zfill(4)}"
                        exec.submit(self.download_file, u, train_dir / fname, pbar)
                    # Fill Val
                    for i, u in enumerate(v_urls):
                        fname = f"{clean_name}_{str(count_v + i + 1 + TRAIN_COUNT).zfill(4)}"
                        exec.submit(self.download_file, u, val_dir / fname, pbar)

            time.sleep(2) # Prevent API lockout

if __name__ == "__main__":
    PlantCrawler().run()