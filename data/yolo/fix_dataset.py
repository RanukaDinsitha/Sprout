import os
import shutil
from pathlib import Path

# --- CONFIGURATION ---
# The folder where your 600/150 images are
MAIN_DATASET = Path("Dataset") 
# The folder where your 80/20 extra images are
EXTRA_DATA_SOURCE = Path("images") 

def merge_data():
    splits = ['train', 'val']

    if not EXTRA_DATA_SOURCE.exists():
        print(f"❌ Error: Could not find source folder: {EXTRA_DATA_SOURCE}")
        return

    print(f"🚀 Merging {EXTRA_DATA_SOURCE} into {MAIN_DATASET}...")

    for split in splits:
        source_split = EXTRA_DATA_SOURCE / split
        dest_split = MAIN_DATASET / split

        if not source_split.exists():
            continue

        # Loop through each plant folder (Rose, Annual poa, etc.)
        for plant_folder in source_split.iterdir():
            if not plant_folder.is_dir():
                continue

            plant_name = plant_folder.name
            dest_plant_path = dest_split / plant_name
            dest_plant_path.mkdir(parents=True, exist_ok=True)

            # 1. Count how many images are already in the main dataset
            existing_files = list(dest_plant_path.glob("*.*"))
            start_index = len(existing_files)

            # 2. Get all new files from the extra source
            new_files = list(plant_folder.glob("*.*"))
            
            print(f"📂 {split}/{plant_name}: Adding {len(new_files)} images (Starting at index {start_index + 1})")

            # 3. Move and Rename
            clean_name = plant_name.replace(" ", "_").lower()
            
            for i, file_path in enumerate(new_files):
                new_idx = start_index + i + 1
                extension = file_path.suffix.lower()
                
                # Format: plant_name_0601.jpg
                new_filename = f"{clean_name}_{str(new_idx).zfill(4)}{extension}"
                dest_file_path = dest_plant_path / new_filename

                # Move file (use shutil.copy if you want to keep the originals)
                shutil.move(str(file_path), str(dest_file_path))

    print("\n✅ Merge Complete! Your dataset is now updated and sequentially numbered.")

if __name__ == "__main__":
    merge_data()
