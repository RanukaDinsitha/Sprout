import os
import pprint

# --- CONFIGURATION ---
# Replace with the path to the folder you want to scan
TARGET_FOLDER = os.path.join("wellington_pests")
# The name of the output text file
OUTPUT_FILE = "extracted_folders.txt"
# ---------------------


def extract_folders_to_txt(target_dir, output_path):
    folder_list = []

    # Walk through all directories and subdirectories
    for root, dirs, _files in os.walk(target_dir):
        dirs.sort()
        for folder in dirs:
            # Get the full absolute path of the folder
            full_path = os.path.join(root, folder)
            # Normalize path separators for consistency
            normalized_path = os.path.normpath(full_path)
            folder_list.append(normalized_path)

    # Format the list nicely using pretty-print
    formatted_array = pprint.pformat(folder_list, indent=4, width=120)

    # Write the formatted Python list into a .txt file
    with open(output_path, "w", encoding="utf-8") as f:
        f.write("folder_array = [\n")
        # Strip the opening and closing brackets from pprint output to format cleanly
        f.write(formatted_array[1:-1])
        f.write("\n]")

    print(f"Success! Found {len(folder_list)} folders.")
    print(f"Saved Python array format to: {os.path.abspath(output_path)}")


if __name__ == "__main__":
    extract_folders_to_txt(TARGET_FOLDER, OUTPUT_FILE)
