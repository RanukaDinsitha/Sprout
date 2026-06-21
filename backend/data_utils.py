import tensorflow as tf
import functools


def preprocess_image(image, img_size):
    image = tf.image.resize(image, [img_size, img_size])
    image = tf.cast(image, tf.float32) / 255.0
    return image


def get_augmentation(img_size):
    data_augment = tf.keras.Sequential([
        tf.keras.layers.RandomFlip('horizontal'),
        tf.keras.layers.RandomRotation(0.08),
        tf.keras.layers.RandomZoom(0.08),
    ], name='augmentation')

    def apply(x, training=False):
        if training:
            return data_augment(x, training=True)
        return x

    return apply


def prepare_for_training(ds, batch_size, img_size, shuffle=True):
    autotune = tf.data.AUTOTUNE
    if shuffle:
        ds = ds.shuffle(1000)
    ds = ds.map(lambda x, y: (preprocess_image(x, img_size), y), num_parallel_calls=autotune)
    ds = ds.batch(batch_size).prefetch(autotune)
    return ds


def get_datasets(dataset='cifar10', data_dir=None, img_size=224, batch_size=32):
    if dataset == 'cifar10':
        (x_train, y_train), (x_test, y_test) = tf.keras.datasets.cifar10.load_data()
        # Split train into train/val
        val_split = 5000
        x_val, y_val = x_train[-val_split:], y_train[-val_split:]
        x_train, y_train = x_train[:-val_split], y_train[:-val_split]

        train_ds = tf.data.Dataset.from_tensor_slices((x_train, y_train))
        val_ds = tf.data.Dataset.from_tensor_slices((x_val, y_val))
        num_classes = 10
        train_ds = prepare_for_training(train_ds, batch_size, img_size, shuffle=True)
        val_ds = prepare_for_training(val_ds, batch_size, img_size, shuffle=False)
        return train_ds, val_ds, num_classes

    # directory-based dataset: expects train/ and validation/ subfolders, or uses validation_split
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
        class_names = train_ds.class_names
        num_classes = len(class_names)
        # normalize
        train_ds = train_ds.map(lambda x,y: (tf.cast(x, tf.float32)/255.0, y))
        val_ds = val_ds.map(lambda x,y: (tf.cast(x, tf.float32)/255.0, y))
        return train_ds, val_ds, num_classes

    raise ValueError('Unknown dataset: %s' % dataset)
