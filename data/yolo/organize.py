import os
import shutil
import re

TRAIN_DIR = r"C:\Users\ranuk\Downloads\Sprout\data\yolo\images\train"
VAL_DIR = r"C:\Users\ranuk\Downloads\Sprout\data\yolo\images\val"

valid_exts = ('.jpg', '.png', '.jpeg', '.webp', '.JPG', '.PNG', '.JPEG')

def group_by_class(target_dir):
    if not os.path.exists(target_dir):
        return

    # Find all image files directly in the target directory
    images = [f for f in os.listdir(target_dir) if f.endswith(valid_exts)]
    
    if not images:
        print(f"No loose images found in {os.path.basename(target_dir)}.")
        return

    print(f"Organizing {len(images)} images in {os.path.basename(target_dir)}...")
    
    for img in images:
        src = os.path.join(target_dir, img)
        
        # Extract class name from image filename prefix (e.g., 'Annual_poa_01.jpg' -> 'Annual_poa')
        match = re.match(r"^(.*?)(?:_\d+|\.\w+$)", img)
        class_name = match.group(1).rstrip('_') if match else "unknown_class"

        # Create subfolder for class
        class_folder = os.path.join(target_dir, class_name)
        os.makedirs(class_folder, exist_ok=True)
        
        # Move image into its class subfolder
        dst = os.path.join(class_folder, img)
        shutil.move(src, dst)

    print(f"Finished organizing {os.path.basename(target_dir)}!")

# Process both train and val folders
group_by_class(TRAIN_DIR)
group_by_class(VAL_DIR)