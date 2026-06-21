"""Prepare dataset: copy images from a parent folder of plant-class subfolders
into a train/ and validation/ split with class-named folders.

Example:
  python prepare_dataset.py --source_dir raw_plants --dest_dir dataset_prepared \
    --num_classes 79 --images_per_class 100 --val_split 0.2
"""
import argparse
import os
import random
import shutil
from pathlib import Path


IMG_EXTS = {'.jpg', '.jpeg', '.png', '.bmp', '.gif', '.tif', '.tiff'}


def list_class_dirs(source_dir):
    p = Path(source_dir)
    return [d.name for d in sorted(p.iterdir()) if d.is_dir()]


def gather_images_for_class(source_dir, class_name):
    class_path = Path(source_dir) / class_name
    files = [p for p in class_path.iterdir() if p.is_file() and p.suffix.lower() in IMG_EXTS]
    return files


def prepare(source_dir, dest_dir, num_classes=79, images_per_class=100, val_split=0.2, test_split=0.0, seed=1337):
    source_dir = Path(source_dir)
    dest_dir = Path(dest_dir)
    random.seed(seed)

    classes = list_class_dirs(source_dir)
    if len(classes) < num_classes:
        print(f'Warning: only found {len(classes)} classes but num_classes={num_classes}')
        chosen = classes
    else:
        chosen = classes[:num_classes]

    print(f'Preparing {len(chosen)} classes into {dest_dir} (images_per_class={images_per_class})')

    for cls in chosen:
        imgs = gather_images_for_class(source_dir, cls)
        if not imgs:
            print(f'  Skipping class {cls}: no images found')
            continue

        imgs = list(imgs)
        random.shuffle(imgs)
        imgs = imgs[:images_per_class]

        n_val = int(len(imgs) * val_split)
        n_test = int(len(imgs) * test_split)
        n_train = len(imgs) - n_val - n_test

        train_imgs = imgs[:n_train]
        val_imgs = imgs[n_train:n_train + n_val]
        test_imgs = imgs[n_train + n_val:]

        for split_name, split_imgs in (('train', train_imgs), ('val', val_imgs), ('test', test_imgs)):
            if not split_imgs:
                continue
            out_dir = dest_dir / split_name / cls
            out_dir.mkdir(parents=True, exist_ok=True)
            for src in split_imgs:
                dst = out_dir / src.name
                # avoid overwriting same filename
                if dst.exists():
                    base, ext = src.stem, src.suffix
                    i = 1
                    while True:
                        candidate = out_dir / f"{base}_{i}{ext}"
                        if not candidate.exists():
                            dst = candidate
                            break
                        i += 1
                shutil.copy2(src, dst)

        print(f'  Class {cls}: train={len(train_imgs)} val={len(val_imgs)} test={len(test_imgs)}')

    print('Done.')


def main():
    p = argparse.ArgumentParser()
    p.add_argument('--source_dir', required=True, help='Parent folder containing class-named subfolders')
    p.add_argument('--dest_dir', default='dataset_prepared', help='Destination folder for train/val/test splits')
    p.add_argument('--num_classes', type=int, default=79)
    p.add_argument('--images_per_class', type=int, default=100)
    p.add_argument('--val_split', type=float, default=0.2)
    p.add_argument('--test_split', type=float, default=0.0)
    p.add_argument('--seed', type=int, default=1337)
    args = p.parse_args()

    prepare(args.source_dir, args.dest_dir, num_classes=args.num_classes,
            images_per_class=args.images_per_class, val_split=args.val_split,
            test_split=args.test_split, seed=args.seed)


if __name__ == '__main__':
    main()
