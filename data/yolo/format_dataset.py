import os
import shutil
import re
from pathlib import Path

# --- CONFIGURATION ---
ROOT_FOLDER = Path("Dataset")
TARGETS = {"train": 600, "val": 150}

def normalize_name(name):
    """
    Standardizes folder names to find duplicates.
    Example: "Old_man's_beard" and "old mans beard" both become "old_mans_beard"
    """
    # 1. Lowercase
    n = name.lower()
    # 2. Replace weird apostrophes/quotes
    n = n.replace("’", "").replace("'", "")
    # 3. Replace dashes and spaces with underscores
    n = re.sub(r'[- ]+', '_', n)
    # 4. Remove any double underscores
    n = re.sub(r'_+', '_', n)
    return n.strip('_')

def unify_and_reindex():
    for split, limit in TARGETS.items():
        split_path = ROOT_FOLDER / split
        if not split_path.exists(): continue

        print(f"\n📂 Auditing {split} split...")
        
        # Dictionary to track unified names: { 'old_mans_beard': [Path1, Path2] }
        unified_groups = {}

        for folder in split_path.iterdir():
            if folder.is_dir():
                norm = normalize_name(folder.name)
                if norm not in unified_groups:
                    unified_groups[norm] = []
                unified_groups[norm].append(folder)

        # Process each group
        for norm_name, folders in unified_groups.items():
            # Create the final "master" folder
            master_folder = split_path / norm_name
            master_folder.mkdir(parents=True, exist_ok=True)

            # Move all files from all variants into the master folder
            all_images = []
            for fld in folders:
                for img in fld.iterdir():
                    if img.is_file():
                        all_images.append(img)

            print(f"  > {norm_name}: Found {len(folders)} variants. Consolidating {len(all_images)} total images...")

            # Sequential Rename & Move
            # We move them to a temp folder first to avoid overwriting issues if master is one of the variants
            temp_path = split_path / f"temp_{norm_name}"
            temp_path.mkdir(parents=True, exist_ok=True)

            for i, img_path in enumerate(all_images):
                ext = img_path.suffix.lower()
                if ext not in ['.jpg', '.jpeg', '.png', '.webp']: ext = '.jpg'
                
                # Maintain the naming convention: plant_name_0001.jpg
                new_name = f"{norm_name}_{str(i+1).zfill(4)}{ext}"
                shutil.move(str(img_path), str(temp_path / new_name))

            # Cleanup: Delete the old variant folders
            for fld in folders:
                if fld.exists():
                    shutil.rmtree(fld)

            # Move temp files to the final master folder
            temp_path.rename(master_folder)

            # Final Step: Trim to exactly the limit (600 or 150)
            final_files = sorted(list(master_folder.glob("*.*")))
            if len(final_files) > limit:
                print(f"    ✂️ Trimming {len(final_files) - limit} excess images.")
                for extra in final_files[limit:]:
                    extra.unlink()
            elif len(final_files) < limit:
                print(f"    ⚠️ Warning: Only {len(final_files)}/{limit} images found for {norm_name}.")

if __name__ == "__main__":
    unify_and_reindex()
    print("\n✅ Dataset Unification Complete! All 'double' folders are merged.")
