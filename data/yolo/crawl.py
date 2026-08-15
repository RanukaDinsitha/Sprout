import os
import logging
from icrawler.builtin import BingImageCrawler
from tqdm import tqdm
import time

# --- CONFIGURATION ---
DATA_DIRS = [os.path.join("images", "train"), os.path.join("images", "val")] 
TRAIN_TARGET = 800
VAL_TARGET = 200
THREADS = 20  # Maximize your 46.5 MiB/s line

# Silence icrawler's internal chatter to keep our UI clean
logging.getLogger('icrawler').setLevel(logging.CRITICAL)

def format_and_clean(folder_path, class_name):
    """
    1. Deletes files that aren't images.
    2. Renames generic icrawler names (000001.jpg) to ClassName_0001.jpg
    """
    files = sorted(os.listdir(folder_path))
    valid_exts = ('.jpg', '.jpeg', '.png', '.webp')
    
    # First, delete non-image trash
    for f in files:
        if not f.lower().endswith(valid_exts):
            try: os.remove(os.path.join(folder_path, f))
            except: pass

    # Second, do a sequential rename to fix the "mess"
    files = sorted([f for f in os.listdir(folder_path) if f.lower().endswith(valid_exts)])
    for i, f in enumerate(files):
        ext = os.path.splitext(f)[1].lower()
        new_name = f"{class_name}_{i:04d}{ext}"
        if f != new_name:
            old_p = os.path.join(folder_path, f)
            new_p = os.path.join(folder_path, new_name)
            if os.path.exists(new_p): os.remove(new_p) # Avoid collisions
            os.rename(old_p, new_p)
            
    return len(os.listdir(folder_path))

def run_downloader():
    # Identify classes
    classes = set()
    for d in DATA_DIRS:
        if os.path.exists(d):
            classes.update([f for f in os.listdir(d) if os.path.isdir(os.path.join(d, f))])
    
    classes = sorted(list(classes))
    
    # Progress bar pinned to bottom
    overall_pbar = tqdm(total=len(classes), desc="OVERALL PROGRESS", position=0, leave=True)

    for plant_name in classes:
        # Visual Separator for the logs
        overall_pbar.write("-" * 60)
        overall_pbar.write(f"📂 TARGETING CLASS: {plant_name}")
        overall_pbar.write("-" * 60)

        for root_dir in DATA_DIRS:
            target = TRAIN_TARGET if 'train' in root_dir.lower() else VAL_TARGET
            folder = os.path.join(root_dir, plant_name)
            
            if not os.path.exists(folder): os.makedirs(folder)

            # 1. Clean up existing "mess" and count
            current_count = format_and_clean(folder, plant_name)
            needed = target - current_count

            if needed > 0:
                overall_pbar.write(f"   📥 Downloading {needed} images into {os.path.basename(root_dir)}...")
                
                crawler = BingImageCrawler(downloader_threads=THREADS, storage={'root_dir': folder})
                
                # Start crawl
                crawler.crawl(keyword=f"{plant_name} plant", max_num=needed)
                
                # 2. Immediately format the new downloads
                format_and_clean(folder, plant_name)
            else:
                overall_pbar.write(f"   ✅ {os.path.basename(root_dir)} folder is already full.")

        # Move the progress bar forward
        overall_pbar.update(1)

    overall_pbar.close()
    print("\n" + "="*60)
    print("FINISHED: All classes formatted to ClassName_XXXX.jpg")
    print("="*60)

if __name__ == "__main__":
    run_downloader()