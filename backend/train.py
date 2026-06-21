import argparse
import os
import tensorflow as tf
from backend.data_utils import get_datasets, get_augmentation
from backend.model import build_model


def parse_args():
    p = argparse.ArgumentParser()
    p.add_argument('--data_dir', default=None, help='Path to image folder (train/val split)')
    p.add_argument('--dataset', default='cifar10', choices=['cifar10','dir'], help='Which dataset to use')
    p.add_argument('--img_size', type=int, default=224)
    p.add_argument('--batch_size', type=int, default=32)
    p.add_argument('--epochs', type=int, default=30)
    p.add_argument('--output_dir', default='outputs')
    p.add_argument('--fine_tune_at', type=int, default=100)
    return p.parse_args()


def main():
    args = parse_args()
    os.makedirs(args.output_dir, exist_ok=True)

    train_ds, val_ds, num_classes = get_datasets(dataset=args.dataset,
                                               data_dir=args.data_dir,
                                               img_size=args.img_size,
                                               batch_size=args.batch_size)

    augmentation = get_augmentation(args.img_size)

    model = build_model(num_classes=num_classes, img_size=args.img_size, fine_tune_at=args.fine_tune_at)
    model.compile(optimizer=tf.keras.optimizers.Adam(1e-4),
                  loss='sparse_categorical_crossentropy',
                  metrics=['accuracy'])

    callbacks = [
        tf.keras.callbacks.ModelCheckpoint(os.path.join(args.output_dir, 'best.h5'), save_best_only=True, monitor='val_accuracy', mode='max'),
        tf.keras.callbacks.ReduceLROnPlateau(monitor='val_loss', factor=0.5, patience=3),
        tf.keras.callbacks.EarlyStopping(monitor='val_loss', patience=8, restore_best_weights=True)
    ]

    autotune = tf.data.AUTOTUNE
    train_ds = train_ds.map(lambda x,y: (augmentation(x, training=True), y), num_parallel_calls=autotune)
    train_ds = train_ds.prefetch(autotune)
    val_ds = val_ds.prefetch(autotune)

    history = model.fit(train_ds, epochs=args.epochs, validation_data=val_ds, callbacks=callbacks)

    model.save(os.path.join(args.output_dir, 'final_model'))
    print('Training finished. Artifacts in', args.output_dir)


if __name__ == '__main__':
    main()
