import argparse
import os
import random
import shutil
import sys
from pathlib import Path

if os.getenv('USE_CPU_ONLY', '0') == '1' or '--use_cpu' in sys.argv or '--cpu' in sys.argv:
    os.environ['CUDA_VISIBLE_DEVICES'] = '-1'

import tensorflow as tf


IMG_EXTS = {'.jpg', '.jpeg', '.png', '.bmp', '.gif', '.tif', '.tiff'}


def preprocess_image(image, img_size):
    image = tf.image.resize(image, [img_size, img_size])
    image = tf.cast(image, tf.float32) / 255.0
    return image


def get_augmentation(img_size):
    data_augment = tf.keras.Sequential([
        tf.keras.layers.RandomFlip('horizontal'),
        tf.keras.layers.RandomRotation(0.12),
        tf.keras.layers.RandomZoom(0.1),
        tf.keras.layers.RandomContrast(0.1),
    ], name='augmentation')

    def apply(x, training=False):
        if training:
            return data_augment(x, training=True)
        return x

    return apply


def prepare_for_training(ds, batch_size, img_size, shuffle=True, num_parallel_calls=tf.data.AUTOTUNE, prefetch_buffer=tf.data.AUTOTUNE):
    if shuffle:
        ds = ds.shuffle(1000)
    ds = ds.map(lambda x, y: (preprocess_image(x, img_size), y), num_parallel_calls=num_parallel_calls)
    ds = ds.batch(batch_size).prefetch(prefetch_buffer)
    return ds


def get_datasets(dataset='cifar10', data_dir=None, img_size=224, batch_size=32, num_parallel_calls=tf.data.AUTOTUNE, prefetch_buffer=tf.data.AUTOTUNE):
    if dataset == 'cifar10':
        (x_train, y_train), _ = tf.keras.datasets.cifar10.load_data()
        val_split = 5000
        x_val, y_val = x_train[-val_split:], y_train[-val_split:]
        x_train, y_train = x_train[:-val_split], y_train[:-val_split]

        train_ds = tf.data.Dataset.from_tensor_slices((x_train, y_train))
        val_ds = tf.data.Dataset.from_tensor_slices((x_val, y_val))
        num_classes = 10

        train_ds = prepare_for_training(
            train_ds,
            batch_size,
            img_size,
            shuffle=True,
            num_parallel_calls=num_parallel_calls,
            prefetch_buffer=prefetch_buffer)
        val_ds = prepare_for_training(
            val_ds,
            batch_size,
            img_size,
            shuffle=False,
            num_parallel_calls=num_parallel_calls,
            prefetch_buffer=prefetch_buffer)
        return train_ds, val_ds, num_classes

    if dataset == 'dir':
        if not data_dir:
            raise ValueError('data_dir is required for dataset=dir')

        train_ds = tf.keras.preprocessing.image_dataset_from_directory(
            data_dir,
            labels='inferred',
            batch_size=batch_size,
            image_size=(img_size, img_size),
            validation_split=0.2,
            subset='training',
            seed=1337)
        val_ds = tf.keras.preprocessing.image_dataset_from_directory(
            data_dir,
            labels='inferred',
            batch_size=batch_size,
            image_size=(img_size, img_size),
            validation_split=0.2,
            subset='validation',
            seed=1337)

        num_classes = len(train_ds.class_names)
        train_ds = train_ds.map(lambda x, y: (tf.cast(x, tf.float32) / 255.0, y), num_parallel_calls=num_parallel_calls)
        train_ds = train_ds.shuffle(1000)
        val_ds = val_ds.map(lambda x, y: (tf.cast(x, tf.float32) / 255.0, y), num_parallel_calls=num_parallel_calls)
        train_ds = train_ds.prefetch(prefetch_buffer)
        val_ds = val_ds.prefetch(prefetch_buffer)
        return train_ds, val_ds, num_classes

    raise ValueError(f'Unknown dataset: {dataset}')


def build_model(num_classes, img_size=224, fine_tune_at=None, dropout=0.3):
    inputs = tf.keras.Input(shape=(img_size, img_size, 3))
    base_model = tf.keras.applications.EfficientNetB0(
        include_top=False, weights='imagenet', input_tensor=inputs)
    base_model.trainable = False

    x = base_model.output
    x = tf.keras.layers.GlobalAveragePooling2D()(x)
    x = tf.keras.layers.BatchNormalization()(x)
    x = tf.keras.layers.Dropout(dropout)(x)
    outputs = tf.keras.layers.Dense(num_classes, activation='softmax')(x)
    model = tf.keras.Model(inputs, outputs)

    if fine_tune_at is not None:
        base_model.trainable = True
        for layer in base_model.layers[:fine_tune_at]:
            layer.trainable = False

    return model


def list_class_dirs(source_dir):
    p = Path(source_dir)
    return [d.name for d in sorted(p.iterdir()) if d.is_dir()]


def gather_images_for_class(source_dir, class_name):
    class_path = Path(source_dir) / class_name
    return [p for p in class_path.iterdir() if p.is_file() and p.suffix.lower() in IMG_EXTS]


def prepare_dataset(source_dir, dest_dir, num_classes=79, images_per_class=100, val_split=0.2, test_split=0.0, seed=1337):
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


def parse_args():
    parser = argparse.ArgumentParser(description='Prepare or train image classification models.')
    subparsers = parser.add_subparsers(dest='command', required=True)

    train_parser = subparsers.add_parser('train', help='Train a model')
    train_parser.add_argument('--data_dir', default='./wellington_pests', help='Path to image folder (directory dataset root)')
    train_parser.add_argument('--dataset', default='cifar10', choices=['cifar10', 'dir'], help='Dataset to use for training')
    train_parser.add_argument('--img_size', type=int, default=224)
    train_parser.add_argument('--batch_size', type=int, default=16, help='Batch size for CPU training')
    train_parser.add_argument('--epochs', type=int, default=80)
    train_parser.add_argument('--output_dir', default='outputs')
    train_parser.add_argument('--learning_rate', type=float, default=1e-4)
    train_parser.add_argument('--dropout', type=float, default=0.3)
    train_parser.add_argument('--fine_tune_at', type=int, default=150)
    train_parser.add_argument('--early_stopping_patience', type=int, default=8)
    train_parser.add_argument('--reduce_lr_patience', type=int, default=3)
    train_parser.add_argument('--num_parallel_calls', type=int, default=-1, help='Number of parallel calls for dataset mapping; -1 means AUTOTUNE')
    train_parser.add_argument('--prefetch_buffer', type=int, default=-1, help='Dataset prefetch buffer size; -1 means AUTOTUNE')
    train_parser.add_argument('--use_cpu', action='store_true', help='Force CPU-only execution')
    train_parser.add_argument('--verbose', action='store_true', help='Enable more verbose training logs')

    prepare_parser = subparsers.add_parser('prepare', help='Prepare a directory dataset from raw class folders')
    prepare_parser.add_argument('--source_dir', default='', help='Parent folder containing class-named subfolders')
    prepare_parser.add_argument('--dest_dir', default='dataset_prepared', help='Output root for train/val/test splits')
    prepare_parser.add_argument('--num_classes', type=int, default=79)
    prepare_parser.add_argument('--images_per_class', type=int, default=100)
    prepare_parser.add_argument('--val_split', type=float, default=0.2)
    prepare_parser.add_argument('--test_split', type=float, default=0.0)
    prepare_parser.add_argument('--seed', type=int, default=1337)

    return parser.parse_args()


def run_training(args):
    os.makedirs(args.output_dir, exist_ok=True)

    if args.use_cpu:
        print('Using CPU-only mode. This may be slower but avoids GPU/DirectML runtime issues.')

    num_parallel_calls = tf.data.AUTOTUNE if args.num_parallel_calls < 0 else args.num_parallel_calls
    prefetch_buffer = tf.data.AUTOTUNE if args.prefetch_buffer < 0 else args.prefetch_buffer

    if args.verbose:
        print(f'Training settings: img_size={args.img_size}, batch_size={args.batch_size}, epochs={args.epochs}, '
              f'lr={args.learning_rate}, dropout={args.dropout}, fine_tune_at={args.fine_tune_at}, '
              f'num_parallel_calls={num_parallel_calls}, prefetch_buffer={prefetch_buffer}')

    train_ds, val_ds, num_classes = get_datasets(
        dataset=args.dataset,
        data_dir=args.data_dir,
        img_size=args.img_size,
        batch_size=args.batch_size,
        num_parallel_calls=num_parallel_calls,
        prefetch_buffer=prefetch_buffer)

    model = build_model(
        num_classes=num_classes,
        img_size=args.img_size,
        fine_tune_at=args.fine_tune_at,
        dropout=args.dropout)
    model.compile(
        optimizer=tf.keras.optimizers.Adam(learning_rate=args.learning_rate),
        loss='sparse_categorical_crossentropy',
        metrics=['accuracy'])

    augmentation = get_augmentation(args.img_size)

    callbacks = [
        tf.keras.callbacks.ModelCheckpoint(
            os.path.join(args.output_dir, 'best.h5'),
            save_best_only=True,
            monitor='val_accuracy',
            mode='max'),
        tf.keras.callbacks.ReduceLROnPlateau(
            monitor='val_loss',
            factor=0.5,
            patience=args.reduce_lr_patience),
        tf.keras.callbacks.EarlyStopping(
            monitor='val_loss',
            patience=args.early_stopping_patience,
            restore_best_weights=True)
    ]

    train_ds = train_ds.map(
        lambda x, y: (augmentation(x, training=True), y),
        num_parallel_calls=num_parallel_calls)
    train_ds = train_ds.prefetch(prefetch_buffer)
    val_ds = val_ds.prefetch(prefetch_buffer)

    model.fit(train_ds, epochs=args.epochs, validation_data=val_ds, callbacks=callbacks)
    model.save(os.path.join(args.output_dir, 'final_model.keras'))
    print('Training finished. Artifacts in', args.output_dir)


def run_prepare(args):
    prepare_dataset(
        source_dir=args.source_dir,
        dest_dir=args.dest_dir,
        num_classes=args.num_classes,
        images_per_class=args.images_per_class,
        val_split=args.val_split,
        test_split=args.test_split,
        seed=args.seed)


def main():
    args = parse_args()
    if args.command == 'train':
        run_training(args)
    elif args.command == 'prepare':
        run_prepare(args)


if __name__ == '__main__':
    main()
