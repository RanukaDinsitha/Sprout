
import argparse
import os
import shutil


def parse_args():
    parser = argparse.ArgumentParser(
        description='Convert Keras saved models to TensorFlow.js format.'
    )
    parser.add_argument(
        '--input', '-i',
        default='backend/output/final_model.keras',
        help='Path to the saved Keras model file or directory.',
    )
    parser.add_argument(
        '--output', '-o',
        default='backend/output/tfjs_model',
        help='Output directory for the TensorFlow.js model files.',
    )
    parser.add_argument(
        '--overwrite', '-f',
        action='store_true',
        help='Remove the output directory before conversion if it exists.',
    )
    return parser.parse_args()


def ensure_output_dir(path, overwrite=False):
    if os.path.exists(path):
        if overwrite:
            shutil.rmtree(path)
            os.makedirs(path, exist_ok=True)
        elif not os.path.isdir(path):
            raise RuntimeError(f'Output path exists and is not a directory: {path}')
    else:
        os.makedirs(path, exist_ok=True)


def load_keras_model(path):
    import tensorflow as tf

    if not os.path.exists(path):
        raise FileNotFoundError(f'Keras model not found: {path}')

    return tf.keras.models.load_model(path)


def convert_to_tfjs(input_path, output_dir):
    try:
        import tensorflowjs as tfjs # type: ignore
    except ImportError as exc:
        raise RuntimeError(
            'The tensorflowjs package is required to convert models. Install it with `pip install tensorflowjs`.'
        ) from exc

    model = load_keras_model(input_path)
    tfjs.converters.save_keras_model(model, output_dir)


def main():
    args = parse_args()
    ensure_output_dir(args.output, overwrite=args.overwrite)
    convert_to_tfjs(args.input, args.output)
    print(f'Converted Keras model to TensorFlow.js format in: {os.path.abspath(args.output)}')
    print('Use the generated model.json and binary weight files from that directory in your frontend.')


if __name__ == '__main__':
    main()
