import tensorflow as tf


def build_model(num_classes, img_size=224, base_model_name='EfficientNetB0', fine_tune_at=None, dropout=0.3):
    inputs = tf.keras.Input(shape=(img_size, img_size, 3))
    base_model = tf.keras.applications.EfficientNetB0(include_top=False, weights='imagenet', input_tensor=inputs)
    base_model.trainable = False

    x = base_model.output
    x = tf.keras.layers.GlobalAveragePooling2D()(x)
    x = tf.keras.layers.Dropout(dropout)(x)
    outputs = tf.keras.layers.Dense(num_classes, activation='softmax')(x)
    model = tf.keras.Model(inputs, outputs)

    if fine_tune_at is not None:
        # Unfreeze from the specified layer
        base_model.trainable = True
        for layer in base_model.layers[:fine_tune_at]:
            layer.trainable = False

    return model
