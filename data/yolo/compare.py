import hashlib
import sys
from difflib import unified_diff
from pathlib import Path
import os


def get_file_hash(file_path: Path) -> str:
    """Calculate SHA-256 hash of a file for binary verification."""
    sha256 = hashlib.sha256()
    with open(file_path, "rb") as f:
        while chunk := f.read(8192):
            sha256.update(chunk)
    return sha256.hexdigest()


def compare_text_files(file1: Path, file2: Path):
    """Compare two text files line by line."""
    print(f"\n📝 Comparing text content between lines...")
    with open(file1, "r", encoding="utf-8", errors="ignore") as f1, open(
        file2, "r", encoding="utf-8", errors="ignore"
    ) as f2:
        f1_lines = f1.readlines()
        f2_lines = f2.readlines()

    diff = list(
        unified_diff(
            f1_lines,
            f2_lines,
            fromfile=file1.name,
            tofile=file2.name,
            lineterm="",
        )
    )

    if not diff:
        print("✅ Text files are completely identical!")
    else:
        print("❌ Differences found:")
        for line in diff:
            print(line)


def compare_files(path1: str, path2: str, mode: str = "auto"):
    """Main function to compare metadata, hashes, and contents."""
    file1, file2 = Path(path1), Path(path2)

    if not file1.exists() or not file2.exists():
        print(f"Error: One or both files do not exist.")
        return

    print(f"📊 [File 1] Size: {file1.stat().st_size:,} bytes | {file1.name}")
    print(f"📊 [File 2] Size: {file2.stat().st_size:,} bytes | {file2.name}")

    # Check hashes
    hash1 = get_file_hash(file1)
    hash2 = get_file_hash(file2)
    print(f"🔑 Hash 1: {hash1}")
    print(f"🔑 Hash 2: {hash2}")

    if hash1 == hash2:
        print("\n🏆 Verdict: Files are 100% IDENTICAL.")
        return
    else:
        print("\n⚠️ Verdict: Files are DIFFERENT.")

    # Content breakdown
    is_model_or_binary = any(
        f.suffix in [".pt", ".onnx", ".bin", ".engine", ".pth"]
        for f in (file1, file2)
    )

    if mode == "text" or (mode == "auto" and not is_model_or_binary):
        compare_text_files(file1, file2)
    else:
        print(
            "ℹ️ Binary or weight files detected. Structural differences require deep inspection frameworks."
        )


if __name__ == "__main__":
    # Example usage: Replace paths with your actual filenames
    # compare_files("model_v1.pt", "model_v2.pt", mode="binary")
    compare_files("yolo26m-cls.pt", os.path.join("openvision", "yolo26m-cls.pt"), mode="text")
